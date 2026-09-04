<?php

namespace Tests\Feature\Console\Commands;

use App\Infrastructure\Persistence\Models\ParsedObservationRecord;
use App\Infrastructure\Sources\Ademe\AdemeCsvParser;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class ParseSourceReleaseCommandTest extends TestCase
{
    use LazilyRefreshDatabase;

    private const RAW_OBJECT_KEY = 'sources/ademe/test/raw.csv';

    private const RAW_SHA256 = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';

    private const RELEASE_SHA256 = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

    public function test_creates_an_immutable_artifact_and_lossless_observations(): void
    {
        $this->travelTo('2026-09-04 12:00:00');
        Storage::fake('atlas_raw');
        Storage::fake('atlas_processing');
        $csv = $this->csv([
            $this->row(['Nom base français' => 'Électricité', 'Total poste non décomposé' => '1,25']),
            $this->row([
                'Type Ligne' => 'Poste',
                'Total poste non décomposé' => '0,25',
            ]),
        ]);
        $this->storeAcquiredRawAsset($csv, 2);

        $command = $this->artisan('atlas:source:parse', ['source' => 'ADEME']);

        $command
            ->expectsOutputToContain('Windows-1252')
            ->expectsOutputToContain('2')
            ->expectsOutputToContain('no normalization or canonical write was performed')
            ->assertSuccessful()
            ->run();
        $artifact = DB::table('parsed_artifacts')->first();
        $this->assertNotNull($artifact);
        Storage::disk('atlas_processing')->assertExists($artifact->object_key);
        $this->assertSame(2, $artifact->row_count);
        $this->assertSame(AdemeCsvParser::PARSER_VERSION, $artifact->parser_version);
        $this->assertSame(AdemeCsvParser::schemaSha256(), $artifact->schema_sha256);
        $this->assertDatabaseCount('parsed_observations', 2);
        $observation = ParsedObservationRecord::query()
            ->where('source_row', 2)
            ->firstOrFail();
        $this->assertSame('Électricité', $observation->fields['Nom base français']);
        $this->assertSame('1,25', $observation->fields['Total poste non décomposé']);
        $this->assertDatabaseHas('ingestion_runs', [
            'phase' => 'parse_source',
            'status' => 'completed',
        ]);
    }

    public function test_reuses_the_existing_artifact_for_the_same_raw_asset_and_parser(): void
    {
        $this->travelTo('2026-09-04 12:00:00');
        Storage::fake('atlas_raw');
        Storage::fake('atlas_processing');
        $csv = $this->csv([$this->row()]);
        $this->storeAcquiredRawAsset($csv, 1);

        $this->artisan('atlas:source:parse', ['source' => 'ADEME'])
            ->assertSuccessful()
            ->run();
        $command = $this->artisan('atlas:source:parse', ['source' => 'ADEME']);

        $command
            ->expectsOutputToContain('already parsed')
            ->assertSuccessful()
            ->run();
        $this->assertDatabaseCount('parsed_artifacts', 1);
        $this->assertDatabaseCount('parsed_observations', 1);
        $this->assertSame(1, DB::table('ingestion_runs')->where('phase', 'parse_source')->count());
    }

    public function test_records_a_permanent_failure_without_partial_observations(): void
    {
        $this->travelTo('2026-09-04 12:00:00');
        Storage::fake('atlas_raw');
        Storage::fake('atlas_processing');
        $csv = $this->csv([
            $this->row(['Total poste non décomposé' => 'invalid']),
        ]);
        $this->storeAcquiredRawAsset($csv, 1);

        $command = $this->artisan('atlas:source:parse', ['source' => 'ADEME']);

        $command
            ->expectsOutputToContain('contains an invalid decimal at record 2')
            ->assertExitCode(2)
            ->run();
        $this->assertDatabaseCount('parsed_artifacts', 0);
        $this->assertDatabaseCount('parsed_observations', 0);
        $this->assertDatabaseHas('ingestion_runs', [
            'phase' => 'parse_source',
            'status' => 'failed',
            'failure_code' => 'SourceContractViolation',
        ]);
    }

    /**
     * @param  list<array<string, string>>  $rows
     */
    private function csv(array $rows): string
    {
        $stream = fopen('php://temp', 'w+b');

        if (! is_resource($stream)) {
            $this->fail('Temporary CSV stream could not be created.');
        }

        fputcsv($stream, AdemeCsvParser::EXPECTED_HEADERS, ';', '"', '');

        foreach ($rows as $row) {
            fputcsv($stream, array_values($row), ';', '"', '');
        }

        rewind($stream);
        $content = stream_get_contents($stream);
        fclose($stream);

        return mb_convert_encoding($content, 'Windows-1252', 'UTF-8');
    }

    /**
     * @param  array<string, string>  $overrides
     * @return array<string, string>
     */
    private function row(array $overrides = []): array
    {
        return array_replace(array_fill_keys(AdemeCsvParser::EXPECTED_HEADERS, ''), [
            'Type Ligne' => 'Elément',
            "Identifiant de l'élément" => '100',
            'Structure' => 'élément non décomposé',
            "Type de l'élément" => "Facteur d'émission",
            "Statut de l'élément" => 'Valide générique',
        ], $overrides);
    }

    private function storeAcquiredRawAsset(string $csv, int $reportedRows): void
    {
        $now = now();
        $sourceId = '01991a75-caa5-72ef-88d0-bdb732624a10';
        $releaseId = '01991a75-caa5-72ef-88d0-bdb732624a11';
        $runId = '01991a75-caa5-72ef-88d0-bdb732624a12';
        $rawAssetId = '01991a75-caa5-72ef-88d0-bdb732624a13';

        Storage::disk('atlas_raw')->put(self::RAW_OBJECT_KEY, $csv);
        DB::table('sources')->insert([
            'id' => $sourceId,
            'code' => 'ADEME',
            'name' => 'ADEME Base Carbone',
            'publisher' => 'ADEME',
            'status' => 'active',
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('source_releases')->insert([
            'id' => $releaseId,
            'source_id' => $sourceId,
            'dataset_id' => 'base-carboner',
            'version' => '23.6',
            'revision_sha256' => self::RELEASE_SHA256,
            'reported_row_count' => $reportedRows,
            'asset_url' => 'https://data.ademe.fr/test.csv',
            'file_name' => 'Base_Carbone_V23.6.csv',
            'file_size' => strlen($csv),
            'upstream_checksum_algorithm' => 'md5',
            'upstream_checksum' => md5($csv),
            'license_title' => 'Licence Ouverte / Open Licence',
            'discovered_at' => $now,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('ingestion_runs')->insert([
            'id' => $runId,
            'source_id' => $sourceId,
            'source_release_id' => $releaseId,
            'idempotency_key' => str_repeat('c', 64),
            'phase' => 'acquire_raw',
            'status' => 'completed',
            'started_at' => $now,
            'completed_at' => $now,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
        DB::table('raw_assets')->insert([
            'id' => $rawAssetId,
            'source_release_id' => $releaseId,
            'ingestion_run_id' => $runId,
            'disk' => 'atlas_raw',
            'object_key' => self::RAW_OBJECT_KEY,
            'original_file_name' => 'Base_Carbone_V23.6.csv',
            'source_url' => 'https://data.ademe.fr/test.csv',
            'media_type' => 'text/csv',
            'file_size' => strlen($csv),
            'sha256' => self::RAW_SHA256,
            'upstream_checksum_algorithm' => 'md5',
            'upstream_checksum' => md5($csv),
            'downloaded_at' => $now,
            'created_at' => $now,
            'updated_at' => $now,
        ]);
    }
}
