<?php

namespace App\Application\Candidate;

use App\Application\Contracts\CandidateBuildRepository;
use App\Application\Contracts\CandidateDiffRulesetLoader;
use App\Application\Contracts\CandidateEntityReader;
use App\Application\Contracts\CandidateMappingPolicyLoader;
use App\Application\Contracts\CandidateRecordMemberWriter;
use App\Application\Contracts\CandidateReleaseComparison;
use App\Application\Contracts\CanonicalJson;
use App\Application\Contracts\CatalogSnapshotLoader;
use App\Application\Contracts\LicenseSnapshotLoader;
use App\Application\Contracts\PreviousCandidatePackageReader;
use App\Domain\Candidate\CandidateBuildResult;
use App\Domain\Candidate\CandidatePackageContext;
use App\Domain\Candidate\CandidateRecordMember;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Catalog\CatalogType;
use DateTimeImmutable;
use Illuminate\Support\Str;

final readonly class PrepareCandidatePackage
{
    public function __construct(
        private CandidateBuildRepository $repository,
        private BuildCandidateEntityMemberFromArtifact $entityMember,
        private CatalogSnapshotLoader $catalogs,
        private LicenseSnapshotLoader $licenses,
        private ValidateCandidateDataset $validate,
        private CandidateEntityReader $entities,
        private CandidateReleaseComparison $comparison,
        private CandidateDiffRulesetLoader $diffRules,
        private PreviousCandidatePackageReader $previous,
        private CandidateRecordMemberWriter $members,
        private BuildEmptyRelationshipMember $relationships,
        private BuildCandidatePackage $build,
        private PersistCandidatePackage $persist,
        private CanonicalJson $json,
        private CandidateMappingPolicyLoader $mapping,
    ) {}

    public function handle(array $plan, string $storageProfile): CandidateBuildResult
    {
        $mappingIdentity = $this->mapping->identity();
        $keys = array_keys($plan);
        sort($keys);
        if ($keys !== ['license_descriptor_path', 'license_descriptor_sha256', 'normalized_artifact_id', 'previous_package_id', 'publisher', 'schema_version']
            || $plan['schema_version'] !== 'atlas-candidate-build/v1'
            || ! is_array($plan['publisher']) || ! is_string($plan['normalized_artifact_id'])
            || ! is_string($plan['license_descriptor_path']) || ! is_string($plan['license_descriptor_sha256'])
            || ($plan['previous_package_id'] !== null && ! is_string($plan['previous_package_id']))) {
            throw new CandidateContractViolation('Invalid candidate build plan.');
        }
        $input = $this->repository->input($plan['normalized_artifact_id']);
        $unit = $this->catalogs->load(CatalogType::Unit);
        $geography = $this->catalogs->load(CatalogType::Geography);
        $license = $this->licenses->load($plan['license_descriptor_path'], $plan['license_descriptor_sha256'], [
            ...$input->source, 'release_revision_sha256' => $input->release['revision_sha256'],
        ]);
        if ($license->license['name'] !== $input->licenseTitle) {
            throw new CandidateContractViolation('License evidence does not match the discovered source license.');
        }
        $temporary = [];
        $runId = null;
        try {
            $entityMember = $this->entityMember->handle($input->artifact);
            $temporary[] = $entityMember->temporaryPath;
            $validated = $this->validate->handle($entityMember, $unit, $geography, $license, $input->rawAssets, $input->normalizedArtifactId, $this->repository->normalizationFindings($input->normalizedArtifactId));
            $temporary[] = $validated->findings->temporaryPath;
            $this->repository->recordValidation($input->normalizedArtifactId, $validated);
            $receipt = $validated->receipt;
            if ($receipt->packageBlocked) {
                return new CandidateBuildResult($receipt, null);
            }
            $previous = null;
            if ($plan['previous_package_id'] !== null) {
                $previous = $this->previous->entities($plan['previous_package_id'], $input->source);
                $temporary[] = $previous->temporaryPath;
            }
            $summary = ['added' => 0, 'changed' => 0, 'unchanged' => 0, 'removed' => 0];
            $diffs = $this->comparison->compare($this->entities->read($entityMember), $previous === null ? [] : $this->entities->read($previous));
            $records = static function () use ($diffs, &$summary): \Generator {
                foreach ($diffs as $diff) {
                    $summary[$diff->classification]++;
                    yield $diff->toRecord();
                }
            };
            $diffMember = $this->members->write(CandidateRecordMember::SourceDiff, $records());
            $temporary[] = $diffMember->temporaryPath;
            $relationshipMember = $this->relationships->handle();
            $temporary[] = $relationshipMember->temporaryPath;
            $runIdentity = hash('sha256', $this->json->encode([
                'phase' => 'build_candidate', 'artifact_id' => $input->normalizedArtifactId, 'validation' => $receipt->identity,
                'plan' => $plan, 'mapping' => $mappingIdentity, 'diff_ruleset' => $this->diffRules->load()->sha256, 'storage' => $storageProfile,
            ]));
            $runId = $this->repository->begin($input, $runIdentity);
            $context = new CandidatePackageContext(
                packageId: (string) Str::uuid7(), sourceReleaseId: $input->sourceReleaseId,
                source: [...$input->source, 'publisher' => $plan['publisher']], release: $input->release,
                rawAssets: $receipt->rawAssets,
                pipeline: [...$input->pipeline, ...$mappingIdentity, 'validation_ruleset_version' => $receipt->rulesetVersion, 'validation_ruleset_sha256' => $receipt->rulesetSha256],
                catalogSnapshots: $receipt->catalogSnapshots, license: $receipt->license,
                entityCounts: ['emission_factor' => $entityMember->recordCount], previousPackageId: $plan['previous_package_id'],
                sourceDiffSummary: $summary, generatedAt: new DateTimeImmutable, producerRunId: $runId, storageProfile: $storageProfile,
            );
            $package = $this->build->handle($context, [$entityMember, $relationshipMember, $validated->findings, $diffMember], $receipt);
            $temporary[] = $package->artifact->temporaryPath;
            $registered = $this->persist->handle($context, $package);
            $this->repository->finish($runId, 'completed', ['package_id' => $registered->packageId, 'validation_identity' => $receipt->identity]);

            return new CandidateBuildResult($receipt, $registered);
        } catch (\Throwable $exception) {
            if ($runId !== null) {
                $this->repository->finish($runId, 'failed', ['failure_code' => $exception::class]);
            }
            throw $exception;
        } finally {
            foreach ($temporary as $path) {
                if (is_file($path)) {
                    unlink($path);
                }
            }
        }
    }
}
