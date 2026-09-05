<?php

namespace Tests\Support;

use App\Application\Contracts\CandidateContractRegistry;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Catalog\CatalogType;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Illuminate\Support\Str;

final class CandidatePipelineFixture
{
    public static function seed(?array $draft = null): array
    {
        $source = (string) Str::uuid7();
        $release = (string) Str::uuid7();
        $run = (string) Str::uuid7();
        $raw = (string) Str::uuid7();
        $parsed = (string) Str::uuid7();
        $normalized = (string) Str::uuid7();
        $now = '2026-01-01 00:00:00';
        DB::table('sources')->insert(['id' => $source, 'code' => 'TEST_SOURCE', 'name' => 'Test Source', 'status' => 'active', 'created_at' => $now, 'updated_at' => $now]);
        DB::table('source_releases')->insert(['id' => $release, 'source_id' => $source, 'dataset_id' => 'test-dataset', 'version' => '1',
            'revision_sha256' => str_repeat('a', 64), 'reported_row_count' => 1, 'asset_url' => 'https://example.test/raw.csv', 'file_name' => 'raw.csv',
            'file_size' => 8, 'upstream_checksum_algorithm' => 'sha256', 'upstream_checksum' => hash('sha256', 'test raw'),
            'license_title' => 'Test License', 'discovered_at' => $now, 'created_at' => $now, 'updated_at' => $now]);
        DB::table('ingestion_runs')->insert(['id' => $run, 'source_id' => $source, 'source_release_id' => $release,
            'idempotency_key' => hash('sha256', $run), 'phase' => 'normalize_source', 'status' => 'completed', 'started_at' => $now, 'created_at' => $now, 'updated_at' => $now]);
        DB::table('raw_assets')->insert(['id' => $raw, 'source_release_id' => $release, 'ingestion_run_id' => $run, 'disk' => 'atlas_raw',
            'object_key' => 'sources/test/raw.csv', 'original_file_name' => 'raw.csv', 'source_url' => 'https://example.test/raw.csv', 'media_type' => 'text/csv',
            'file_size' => 8, 'sha256' => hash('sha256', 'test raw'), 'upstream_checksum_algorithm' => 'sha256', 'upstream_checksum' => hash('sha256', 'test raw'),
            'downloaded_at' => $now, 'created_at' => $now, 'updated_at' => $now]);
        DB::table('parsed_artifacts')->insert(['id' => $parsed, 'source_release_id' => $release, 'ingestion_run_id' => $run, 'raw_asset_id' => $raw,
            'disk' => 'atlas_processing', 'object_key' => 'parsed/test.ndjson', 'format' => 'ndjson', 'parser_version' => '1.0.0', 'schema_version' => 'test-v1',
            'schema_sha256' => str_repeat('b', 64), 'source_encoding' => 'UTF-8', 'row_count' => 1, 'file_size' => 1, 'sha256' => str_repeat('c', 64), 'created_at' => $now, 'updated_at' => $now]);
        $bytes = json_encode($draft ?? CandidateFixture::draft()->toUnhashedRecord(), JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)."\n";
        $hash = hash('sha256', $bytes);
        $objectKey = 'normalized/sha256/'.$hash.'.ndjson';
        Storage::disk('atlas_processing')->put($objectKey, $bytes);
        $contract = app(CandidateContractRegistry::class)->get(CandidateContract::EntityRecord);
        DB::table('normalized_artifacts')->insert(['id' => $normalized, 'source_release_id' => $release, 'ingestion_run_id' => $run, 'parsed_artifact_id' => $parsed,
            'disk' => 'atlas_processing', 'object_key' => $objectKey, 'format' => 'ndjson', 'normalizer_version' => '1.0.0', 'candidate_schema_version' => '2.0.0',
            'candidate_schema_sha256' => $contract->sha256, 'candidate_count' => 1, 'finding_count' => 0, 'file_size' => strlen($bytes), 'sha256' => $hash,
            'metrics' => '{}', 'created_at' => $now, 'updated_at' => $now]);
        foreach (CatalogType::cases() as $type) {
            $snapshot = CandidateFixture::snapshot($type);
            $descriptor = $snapshot->descriptor;
            $payloadBytes = json_encode($snapshot->payload, JSON_THROW_ON_ERROR);
            $descriptorBytes = json_encode(['schema_version' => $descriptor->schemaVersion, 'owner' => $descriptor->owner, 'catalog' => $type->value,
                'version' => $descriptor->version, 'content_schema_version' => $descriptor->contentSchemaVersion, 'canonicalization' => $descriptor->canonicalization,
                'sha256' => $descriptor->sha256, 'size_bytes' => $descriptor->sizeBytes, 'artifact_path' => $descriptor->artifactPath], JSON_THROW_ON_ERROR);
            Storage::disk('atlas_catalogs')->put($descriptor->artifactPath, $payloadBytes);
            Storage::disk('atlas_catalogs')->put($descriptor->artifactPath.'.manifest.json', $descriptorBytes);
            config(["atlas.catalogs.snapshots.{$type->value}" => ['descriptor_path' => $descriptor->artifactPath.'.manifest.json', 'descriptor_sha256' => hash('sha256', $descriptorBytes)]]);
        }
        $terms = 'Test-only license terms. No production source rights are implied.';
        $termsHash = hash('sha256', $terms);
        $license = ['identifier' => 'test-license', 'name' => 'Test License', 'terms_sha256' => $termsHash,
            'attribution' => 'Test Publisher', 'source_uri' => 'https://example.test/license', 'retrieved_at' => '2026-01-01T00:00:00Z'];
        $descriptorBytes = json_encode(['schema_version' => 'atlas-license-evidence/v1',
            'source' => ['code' => 'TEST_SOURCE', 'dataset_id' => 'test-dataset', 'release_revision_sha256' => str_repeat('a', 64)],
            'license' => $license, 'terms_object_key' => "licenses/sha256/{$termsHash}.terms", 'terms_size_bytes' => strlen($terms)], JSON_THROW_ON_ERROR);
        $descriptorHash = hash('sha256', $descriptorBytes);
        Storage::disk('atlas_processing')->put("licenses/sha256/{$termsHash}.terms", $terms);
        Storage::disk('atlas_processing')->put("licenses/sha256/{$descriptorHash}.json", $descriptorBytes);

        return ['schema_version' => 'atlas-candidate-build/v1', 'normalized_artifact_id' => $normalized,
            'publisher' => ['name' => 'Test Publisher', 'identifier' => null, 'homepage' => 'https://example.test'],
            'license_descriptor_path' => "licenses/sha256/{$descriptorHash}.json", 'license_descriptor_sha256' => $descriptorHash, 'previous_package_id' => null];
    }
}
