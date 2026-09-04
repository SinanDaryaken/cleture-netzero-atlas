<?php

namespace Tests\Feature\Console\Commands;

use App\Infrastructure\Sources\Ademe\AdemeCsvParser;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class NormalizeSourceReleaseCommandTest extends TestCase
{
    use LazilyRefreshDatabase;

    private const RAW_OBJECT_KEY = 'sources/ademe/test/raw.csv';

    private const RAW_SHA256 = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';

    private const RELEASE_SHA256 = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

    public function test_creates_an_immutable_candidate_draft_and_persists_findings(): void
    {
        $this->travelTo('2026-09-04 12:00:00');
        Storage::fake('atlas_raw');
        Storage::fake('atlas_processing');
        $csv = $this->csv([
            $this->row([
                'Nom base français' => 'Électricité',
                'Unité français' => 'kgCO2e/kWh',
                'Localisation géographique' => 'France continentale',
                'Total poste non décomposé' => '-1,25',
                'CO2f' => '1,0',
            ]),
            $this->row([
                'Type Ligne' => 'Poste',
                'Type poste' => 'Amont',
                'Nom poste français' => 'Fabrication',
                'Total poste non décomposé' => '0,25',
            ]),
        ]);
        $this->storeAcquiredRawAsset($csv, 2);
        $this->artisan('atlas:source:parse', ['source' => 'ADEME'])->assertSuccessful()->run();

        $command = $this->artisan('atlas:source:normalize', ['source' => 'ADEME']);

        $command
            ->expectsOutputToContain('1')
            ->expectsOutputToContain('no candidate package or canonical write was performed')
            ->assertSuccessful()
            ->run();
        $artifact = DB::table('normalized_artifacts')->first();
        $this->assertNotNull($artifact);
        Storage::disk('atlas_processing')->assertExists($artifact->object_key);
        $this->assertSame(1, $artifact->candidate_count);
        $this->assertSame(1, $artifact->finding_count);
        $this->assertDatabaseHas('normalization_findings', [
            'code' => 'negative_total_requires_methodology_review',
            'severity' => 'review',
        ]);
        $this->assertDatabaseHas('ingestion_runs', [
            'phase' => 'normalize_source',
            'status' => 'completed',
        ]);

        $contents = Storage::disk('atlas_processing')->get($artifact->object_key);
        $record = json_decode(trim($contents), true, flags: JSON_THROW_ON_ERROR);
        $this->assertSame('-1.25', $record['primary_quantity']['value']);
        $this->assertSame('unresolved', $record['geography_proposals'][0]['status']);
        $this->assertArrayNotHasKey('record_sha256', $record);
    }

    public function test_reuses_the_existing_artifact_for_the_same_contract_and_normalizer(): void
    {
        $this->travelTo('2026-09-04 12:00:00');
        Storage::fake('atlas_raw');
        Storage::fake('atlas_processing');
        $csv = $this->csv([$this->row([
            'Unité français' => 'kgCO2e/kWh',
            'Total poste non décomposé' => '1',
        ])]);
        $this->storeAcquiredRawAsset($csv, 1);
        $this->artisan('atlas:source:parse', ['source' => 'ADEME'])->assertSuccessful()->run();
        $this->artisan('atlas:source:normalize', ['source' => 'ADEME'])->assertSuccessful()->run();

        $command = $this->artisan('atlas:source:normalize', ['source' => 'ADEME']);

        $command->expectsOutputToContain('already normalized')->assertSuccessful()->run();
        $this->assertDatabaseCount('normalized_artifacts', 1);
        $this->assertSame(1, DB::table('ingestion_runs')->where('phase', 'normalize_source')->count());
    }

    public function test_rejects_a_parsed_artifact_that_changed_after_persistence(): void
    {
        $this->travelTo('2026-09-04 12:00:00');
        Storage::fake('atlas_raw');
        Storage::fake('atlas_processing');
        $csv = $this->csv([$this->row([
            'Unité français' => 'kgCO2e/kWh',
            'Total poste non décomposé' => '1',
        ])]);
        $this->storeAcquiredRawAsset($csv, 1);
        $this->artisan('atlas:source:parse', ['source' => 'ADEME'])->assertSuccessful()->run();
        $parsed = DB::table('parsed_artifacts')->first();
        Storage::disk('atlas_processing')->put($parsed->object_key, "{}\n");

        $command = $this->artisan('atlas:source:normalize', ['source' => 'ADEME']);

        $command->assertExitCode(2)->run();
        $this->assertDatabaseCount('normalized_artifacts', 0);
        $this->assertDatabaseHas('ingestion_runs', [
            'phase' => 'normalize_source',
            'status' => 'failed',
            'failure_code' => 'SourceContractViolation',
        ]);
    }

    /** @param list<array<string, string>> $rows */
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
        $sourceId = '01991a75-caa5-72ef-88d0-bdb732624a20';
        $releaseId = '01991a75-caa5-72ef-88d0-bdb732624a21';
        $runId = '01991a75-caa5-72ef-88d0-bdb732624a22';
        $rawAssetId = '01991a75-caa5-72ef-88d0-bdb732624a23';

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
            'source_updated_at' => $now,
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
