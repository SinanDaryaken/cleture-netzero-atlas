<?php

namespace Tests\Unit\Application\Candidate;

use App\Application\Candidate\BuildCandidatePackage;
use App\Application\Contracts\CandidatePackageIdentityLedger;
use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CandidatePackageContext;
use App\Domain\Candidate\CandidateValidationReceipt;
use App\Infrastructure\Candidate\Rfc8785CanonicalJson;
use App\Infrastructure\Contracts\OpisCandidateSchemaValidator;
use App\Infrastructure\Contracts\PinnedCandidateContractRegistry;
use DateTimeImmutable;
use Tests\TestCase;
use ZipArchive;

final class BuildCandidatePackageTest extends TestCase
{
    public function test_builds_the_same_schema_valid_archive_and_manifest_for_the_same_inputs(): void
    {
        $members = [
            $this->member('entities.ndjson', "{\"candidate_key\":\"one\"}\n", 1),
            $this->member('relationships.ndjson', '', 0),
            $this->member('findings.ndjson', '', 0),
            $this->member('source-diff.ndjson', "{\"classification\":\"added\"}\n", 1),
        ];
        $builder = $this->builder();

        $first = $builder->handle($this->context(), array_reverse($members), $this->receipt($members));
        $second = $builder->handle($this->context(), $members, $this->receipt($members));

        try {
            $zip = new ZipArchive;
            $this->assertTrue($zip->open($first->artifact->temporaryPath));
            $paths = [];

            for ($index = 0; $index < $zip->numFiles; $index++) {
                $paths[] = $zip->getNameIndex($index);
            }

            $zip->close();

            $this->assertSame([
                'entities.ndjson',
                'relationships.ndjson',
                'findings.ndjson',
                'source-diff.ndjson',
            ], $paths);
            $this->assertSame($first->artifact->sha256, $second->artifact->sha256);
            $this->assertSame($first->canonicalManifestJson, $second->canonicalManifestJson);
            $this->assertSame("sha256/{$first->artifact->sha256}.zip", $first->artifact->objectKey);
            $this->assertMatchesRegularExpression('/^sha256:[a-f0-9]{64}$/', $first->manifest['idempotency_key']);
            $this->assertSame(1, $first->manifest['counts']['entities']);
            $this->assertSame(1, $first->manifest['source_diff_summary']['added']);
        } finally {
            unlink($first->artifact->temporaryPath);
            unlink($second->artifact->temporaryPath);

            foreach ($members as $member) {
                unlink($member->temporaryPath);
            }
        }
    }

    private function builder(): BuildCandidatePackage
    {
        $contracts = new PinnedCandidateContractRegistry(
            base_path('resources/contracts/netzero-admin/candidate-v2/contract-manifest.json'),
        );

        return new BuildCandidatePackage(
            contracts: $contracts,
            schemaValidator: new OpisCandidateSchemaValidator($contracts),
            canonicalJson: new Rfc8785CanonicalJson,
            identities: new class implements CandidatePackageIdentityLedger
            {
                public function reserve(string $idempotencyKey, CandidatePackageContext $context): CandidatePackageContext
                {
                    return $context;
                }
            },
        );
    }

    private function context(): CandidatePackageContext
    {
        return new CandidatePackageContext(
            packageId: '018f0c1a-7b2c-7def-8abc-1234567890ab',
            sourceReleaseId: '018f0c1a-7b2c-7def-8abc-1234567890ac',
            source: [
                'code' => 'TEST_SOURCE',
                'dataset_id' => 'dataset-1',
                'publisher' => [
                    'name' => 'Test Publisher',
                    'identifier' => null,
                    'homepage' => 'https://example.test',
                ],
            ],
            release: [
                'version' => '1',
                'revision_sha256' => str_repeat('1', 64),
                'source_published_at' => '2026-09-01T00:00:00+00:00',
            ],
            rawAssets: [
                'set_sha256' => str_repeat('2', 64),
                'asset_count' => 1,
                'assets' => [[
                    'asset_key' => 'sources/test/raw.csv',
                    'sha256' => str_repeat('3', 64),
                    'size_bytes' => 10,
                    'media_type' => 'text/csv',
                    'source_uri' => 'https://example.test/raw.csv',
                    'retrieved_at' => '2026-09-01T01:00:00+00:00',
                ]],
            ],
            pipeline: [
                'parser_version' => '1.0.0',
                'candidate_schema_version' => '2.0.0',
                'parser_schema_fingerprint_sha256' => str_repeat('4', 64),
                'normalizer_version' => '1.0.0',
                'mapping_ruleset_version' => '1.0.0',
                'mapping_ruleset_sha256' => str_repeat('5', 64),
                'validation_ruleset_version' => '1.0.0',
                'validation_ruleset_sha256' => str_repeat('6', 64),
                'canonicalization_version' => 'rfc8785-decimal-string-v1',
            ],
            catalogSnapshots: [
                'unit' => ['version' => 'unit-v1', 'sha256' => str_repeat('7', 64)],
                'geography' => [
                    'owner' => 'NetZeroAdmin',
                    'version' => 'geo-v1',
                    'sha256' => str_repeat('8', 64),
                ],
            ],
            license: [
                'identifier' => 'license-1',
                'name' => 'Test License',
                'terms_sha256' => str_repeat('9', 64),
                'attribution' => 'Test attribution',
                'source_uri' => 'https://example.test/license',
                'retrieved_at' => '2026-09-01T01:00:00+00:00',
            ],
            entityCounts: ['emission_factor' => 1],
            previousPackageId: null,
            sourceDiffSummary: ['added' => 1, 'changed' => 0, 'unchanged' => 0, 'removed' => 0],
            generatedAt: new DateTimeImmutable('2026-09-05T12:00:00+00:00'),
            producerRunId: 'run-1',
            storageProfile: 'atlas_candidates',
        );
    }

    private function receipt(array $members): CandidateValidationReceipt
    {
        $context = $this->context();

        return new CandidateValidationReceipt(str_repeat('a', 64), $members[0]->sha256, $members[2]->sha256,
            $context->pipeline['validation_ruleset_version'], $context->pipeline['validation_ruleset_sha256'],
            $context->catalogSnapshots, $context->license, $context->rawAssets, 1, ['clean' => 1], false);
    }

    private function member(string $path, string $contents, int $recordCount): CandidateArchiveMember
    {
        $temporaryPath = tempnam(sys_get_temp_dir(), 'atlas-package-test-');
        file_put_contents($temporaryPath, $contents);

        return new CandidateArchiveMember(
            path: $path,
            temporaryPath: $temporaryPath,
            sha256: hash('sha256', $contents),
            sizeBytes: strlen($contents),
            recordCount: $recordCount,
        );
    }
}
