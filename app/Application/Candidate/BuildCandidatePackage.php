<?php

namespace App\Application\Candidate;

use App\Application\Contracts\CandidateContractRegistry;
use App\Application\Contracts\CandidatePackageIdentityLedger;
use App\Application\Contracts\CandidateSchemaValidator;
use App\Application\Contracts\CanonicalJson;
use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\CandidatePackageArtifact;
use App\Domain\Candidate\CandidatePackageBuild;
use App\Domain\Candidate\CandidatePackageContext;
use App\Domain\Candidate\CandidateValidationReceipt;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use RuntimeException;
use Throwable;
use ZipArchive;

final readonly class BuildCandidatePackage
{
    private const MEMBER_ORDER = [
        'entities.ndjson',
        'relationships.ndjson',
        'findings.ndjson',
        'source-diff.ndjson',
    ];

    private const ARCHIVE_TIMESTAMP = 315532800;

    public function __construct(
        private CandidateContractRegistry $contracts,
        private CandidateSchemaValidator $schemaValidator,
        private CanonicalJson $canonicalJson,
        private CandidatePackageIdentityLedger $identities,
    ) {}

    /** @param iterable<CandidateArchiveMember> $members */
    public function handle(CandidatePackageContext $context, iterable $members, CandidateValidationReceipt $validation): CandidatePackageBuild
    {
        $this->contracts->assertPackageBuildReady();
        $membersByPath = $this->indexMembers($members);
        $validation->assertPackage($context, $membersByPath);
        $entities = $membersByPath['entities.ndjson'];
        $sourceDiff = $membersByPath['source-diff.ndjson'];

        if (array_sum($context->entityCounts) !== $entities->recordCount) {
            throw new CandidateContractViolation('Candidate package entity count summary does not match its member.');
        }

        if (array_sum($context->sourceDiffSummary) !== $sourceDiff->recordCount) {
            throw new CandidateContractViolation('Candidate package source diff summary does not match its member.');
        }

        if ($entities->recordCount !== $context->sourceDiffSummary['added'] + $context->sourceDiffSummary['changed'] + $context->sourceDiffSummary['unchanged']) {
            throw new CandidateContractViolation('Source diff does not cover all current entities.');
        }

        $artifact = $this->archive($membersByPath);
        $schemaVersion = $this->contracts->get(CandidateContract::PackageManifest)->version;
        $memberManifest = [];

        foreach (self::MEMBER_ORDER as $path) {
            $memberManifest[$this->manifestMemberKey($path)] = $this->memberRecord($membersByPath[$path]);
        }

        $identity = [
            'schema_version' => $schemaVersion,
            'mode' => 'full_snapshot',
            'source' => $context->source,
            'release' => $context->release,
            'raw_assets' => $context->rawAssets,
            'pipeline' => $context->pipeline,
            'catalog_snapshots' => $context->catalogSnapshots,
            'license' => $context->license,
            'artifact_sha256' => $artifact->sha256,
            'members' => $memberManifest,
            'previous_package_id' => $context->previousPackageId,
            'storage_profile' => $context->storageProfile,
            'extensions' => (object) $context->extensions,
        ];
        $idempotencyKey = 'sha256:'.hash('sha256', $this->canonicalJson->encode($identity));
        try {
            $context = $this->identities->reserve($idempotencyKey, $context);
        } catch (Throwable $exception) {
            unlink($artifact->temporaryPath);
            throw $exception;
        }
        $manifest = [
            'schema_version' => $schemaVersion,
            'package_id' => $context->packageId,
            'idempotency_key' => $idempotencyKey,
            'mode' => 'full_snapshot',
            'source' => $context->source,
            'release' => $context->release,
            'raw_assets' => $context->rawAssets,
            'pipeline' => $context->pipeline,
            'catalog_snapshots' => $context->catalogSnapshots,
            'license' => $context->license,
            'artifact' => [
                'storage_profile' => $context->storageProfile,
                'object_key' => $artifact->objectKey,
                'object_version_id' => null,
                'sha256' => $artifact->sha256,
                'size_bytes' => $artifact->sizeBytes,
                'media_type' => CandidatePackageArtifact::MEDIA_TYPE,
            ],
            'members' => $memberManifest,
            'counts' => [
                'entities' => $entities->recordCount,
                'relationships' => $membersByPath['relationships.ndjson']->recordCount,
                'findings' => $membersByPath['findings.ndjson']->recordCount,
                'source_diff' => $sourceDiff->recordCount,
                'by_entity_type' => (object) $context->entityCounts,
            ],
            'previous_package_id' => $context->previousPackageId,
            'source_diff_summary' => $context->sourceDiffSummary,
            'generated_at' => $context->generatedAt->format('Y-m-d\TH:i:s.uP'),
            'producer_run_id' => $context->producerRunId,
            'extensions' => (object) $context->extensions,
        ];

        try {
            $this->schemaValidator->assertValid(CandidateContract::PackageManifest, $manifest);
        } catch (Throwable $exception) {
            unlink($artifact->temporaryPath);

            throw $exception;
        }

        return new CandidatePackageBuild(
            artifact: $artifact,
            manifest: $manifest,
            canonicalManifestJson: $this->canonicalJson->encode($manifest),
        );
    }

    /**
     * @param  iterable<CandidateArchiveMember>  $members
     * @return array<string, CandidateArchiveMember>
     */
    private function indexMembers(iterable $members): array
    {
        $indexed = [];

        foreach ($members as $member) {
            if (! $member instanceof CandidateArchiveMember || isset($indexed[$member->path])) {
                throw new CandidateContractViolation('Candidate package received an invalid or duplicate member.');
            }

            $indexed[$member->path] = $member;
        }

        $paths = array_keys($indexed);
        sort($paths, SORT_STRING);
        $expected = self::MEMBER_ORDER;
        sort($expected, SORT_STRING);

        if ($paths !== $expected) {
            throw new CandidateContractViolation('Candidate package requires exactly the four contracted members.');
        }

        return $indexed;
    }

    /** @param array<string, CandidateArchiveMember> $members */
    private function archive(array $members): CandidatePackageArtifact
    {
        $temporaryPath = tempnam(sys_get_temp_dir(), 'atlas-v2-package-');

        if ($temporaryPath === false) {
            throw new RuntimeException('A temporary candidate package could not be created.');
        }

        $zip = new ZipArchive;

        if ($zip->open($temporaryPath, ZipArchive::OVERWRITE) !== true) {
            unlink($temporaryPath);

            throw new RuntimeException('The temporary candidate package could not be opened.');
        }

        try {
            foreach (self::MEMBER_ORDER as $path) {
                $member = $members[$path];
                if (filesize($member->temporaryPath) !== $member->sizeBytes || ! hash_equals($member->sha256, hash_file('sha256', $member->temporaryPath))) {
                    throw new CandidateContractViolation('Member bytes changed after validation.');
                }
                if (! $zip->addFile($members[$path]->temporaryPath, $path)
                    || ! $zip->setCompressionName($path, ZipArchive::CM_STORE)
                    || ! $zip->setMtimeName($path, self::ARCHIVE_TIMESTAMP)
                    || ! $zip->setExternalAttributesName($path, ZipArchive::OPSYS_UNIX, 0100644 << 16)
                ) {
                    throw new RuntimeException("Candidate package member {$path} could not be archived.");
                }
            }
        } catch (Throwable $exception) {
            $zip->close();
            unlink($temporaryPath);

            throw $exception;
        }

        if (! $zip->close()) {
            unlink($temporaryPath);

            throw new RuntimeException('Candidate package archive could not be finalized.');
        }

        $sizeBytes = filesize($temporaryPath);
        $sha256 = hash_file('sha256', $temporaryPath);

        if (! is_int($sizeBytes) || ! is_string($sha256)) {
            unlink($temporaryPath);

            throw new RuntimeException('Candidate package identity could not be calculated.');
        }

        return new CandidatePackageArtifact(
            temporaryPath: $temporaryPath,
            objectKey: "sha256/{$sha256}.zip",
            sha256: $sha256,
            sizeBytes: $sizeBytes,
        );
    }

    /** @return array<string, int|string> */
    private function memberRecord(CandidateArchiveMember $member): array
    {
        return [
            'path' => $member->path,
            'sha256' => $member->sha256,
            'size_bytes' => $member->sizeBytes,
            'record_count' => $member->recordCount,
            'media_type' => $member->mediaType,
        ];
    }

    private function manifestMemberKey(string $path): string
    {
        return match ($path) {
            'entities.ndjson' => 'entities',
            'relationships.ndjson' => 'relationships',
            'findings.ndjson' => 'findings',
            'source-diff.ndjson' => 'source_diff',
            default => throw new CandidateContractViolation("Unknown candidate package member {$path}."),
        };
    }
}
