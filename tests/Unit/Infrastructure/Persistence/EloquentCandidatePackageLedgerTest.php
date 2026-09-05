<?php

namespace Tests\Unit\Infrastructure\Persistence;

use App\Domain\Candidate\CandidatePackageArtifact;
use App\Domain\Candidate\CandidatePackageBuild;
use App\Domain\Candidate\CandidatePackageContext;
use App\Domain\Candidate\StoredCandidatePackage;
use App\Infrastructure\Persistence\EloquentCandidatePackageLedger;
use DateTimeImmutable;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Support\Facades\DB;
use Tests\TestCase;

final class EloquentCandidatePackageLedgerTest extends TestCase
{
    use LazilyRefreshDatabase;

    public function test_registers_one_package_for_repeated_immutable_facts(): void
    {
        [$sourceReleaseId, $runId] = $this->sourceReleaseAndRun();
        [$context, $package, $storage, $temporaryPath] = $this->packageFacts($sourceReleaseId, $runId);
        $ledger = new EloquentCandidatePackageLedger;

        $first = $ledger->register($context, $package, $storage);
        $second = $ledger->register($context, $package, $storage);

        try {
            $this->assertFalse($first->alreadyExisted);
            $this->assertTrue($second->alreadyExisted);
            $this->assertSame($first->packageId, $second->packageId);
            $this->assertDatabaseCount('candidate_packages', 1);
            $this->assertDatabaseHas('candidate_packages', [
                'id' => $context->packageId,
                'idempotency_key' => $package->manifest['idempotency_key'],
                'archive_sha256' => $storage->archiveSha256,
                'manifest_sha256' => $storage->manifestSha256,
            ]);
        } finally {
            unlink($temporaryPath);
        }
    }

    /** @return array{string, string} */
    private function sourceReleaseAndRun(): array
    {
        $sourceId = '018f0c1a-7b2c-7def-8abc-123456789001';
        $releaseId = '018f0c1a-7b2c-7def-8abc-123456789002';
        $runId = '018f0c1a-7b2c-7def-8abc-123456789003';
        $now = now();
        DB::table('sources')->insert([
            'id' => $sourceId,
            'code' => 'TEST_SOURCE',
            'name' => 'Test Source',
            'status' => 'active',
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('source_releases')->insert([
            'id' => $releaseId,
            'source_id' => $sourceId,
            'dataset_id' => 'dataset-1',
            'version' => '1',
            'revision_sha256' => str_repeat('1', 64),
            'reported_row_count' => 1,
            'asset_url' => 'https://example.test/raw.csv',
            'file_name' => 'raw.csv',
            'file_size' => 10,
            'upstream_checksum_algorithm' => 'sha256',
            'upstream_checksum' => str_repeat('2', 64),
            'license_title' => 'Test License',
            'discovered_at' => $now,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('ingestion_runs')->insert([
            'id' => $runId,
            'source_id' => $sourceId,
            'source_release_id' => $releaseId,
            'idempotency_key' => str_repeat('3', 64),
            'phase' => 'build_candidate',
            'status' => 'completed',
            'started_at' => $now,
            'completed_at' => $now,
            'created_at' => $now,
            'updated_at' => $now,
        ]);

        return [$releaseId, $runId];
    }

    /** @return array{CandidatePackageContext, CandidatePackageBuild, StoredCandidatePackage, string} */
    private function packageFacts(string $sourceReleaseId, string $runId): array
    {
        $temporaryPath = tempnam(sys_get_temp_dir(), 'atlas-ledger-test-');
        file_put_contents($temporaryPath, 'archive');
        $archiveSha256 = hash('sha256', 'archive');
        $manifestJson = '{"idempotency_key":"sha256:'.str_repeat('4', 64).'"}';
        $manifestSha256 = hash('sha256', $manifestJson);
        $artifact = new CandidatePackageArtifact(
            temporaryPath: $temporaryPath,
            objectKey: "sha256/{$archiveSha256}.zip",
            sha256: $archiveSha256,
            sizeBytes: strlen('archive'),
        );
        $package = new CandidatePackageBuild(
            artifact: $artifact,
            manifest: [
                'schema_version' => '2.0.0',
                'idempotency_key' => 'sha256:'.str_repeat('4', 64),
                'counts' => [
                    'entities' => 1,
                    'relationships' => 0,
                    'findings' => 0,
                    'source_diff' => 1,
                    'by_entity_type' => ['emission_factor' => 1],
                ],
                'source_diff_summary' => ['added' => 1, 'changed' => 0, 'unchanged' => 0, 'removed' => 0],
            ],
            canonicalManifestJson: $manifestJson,
        );
        $storage = new StoredCandidatePackage(
            disk: 'candidate_test',
            archiveObjectKey: $artifact->objectKey,
            archiveSha256: $archiveSha256,
            archiveSize: $artifact->sizeBytes,
            manifestObjectKey: "manifests/sha256/{$manifestSha256}.json",
            manifestSha256: $manifestSha256,
            manifestSize: strlen($manifestJson),
            archiveAlreadyExisted: false,
            manifestAlreadyExisted: false,
        );
        $context = new CandidatePackageContext(
            packageId: '018f0c1a-7b2c-7def-8abc-123456789004',
            sourceReleaseId: $sourceReleaseId,
            source: [],
            release: [],
            rawAssets: [],
            pipeline: [],
            catalogSnapshots: [],
            license: [],
            entityCounts: ['emission_factor' => 1],
            previousPackageId: null,
            sourceDiffSummary: ['added' => 1, 'changed' => 0, 'unchanged' => 0, 'removed' => 0],
            generatedAt: new DateTimeImmutable('2026-09-05T12:00:00+00:00'),
            producerRunId: $runId,
            storageProfile: 'candidate_test',
        );

        return [$context, $package, $storage, $temporaryPath];
    }
}
