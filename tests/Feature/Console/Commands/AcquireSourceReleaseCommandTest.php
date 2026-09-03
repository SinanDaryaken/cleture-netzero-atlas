<?php

namespace Tests\Feature\Console\Commands;

use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class AcquireSourceReleaseCommandTest extends TestCase
{
    use LazilyRefreshDatabase;

    private const ASSET_BODY = "fake-ademe-csv\n";

    private const ASSET_MD5 = '22fad33ea3fb87c06ff8c77bf73a2ed5';

    private const ASSET_SHA256 = '13aa9bc10efde2b77c11355de069b41757bdd7664117e594bcc044ce4d9d8771';

    private const DATASET_URL = 'https://data.ademe.fr/data-fair/api/v1/datasets/base-carboner';

    private const ASSET_URL = self::DATASET_URL.'/data-files/Base_Carbone_V23.6.csv';

    public function test_stores_a_verified_release_as_an_immutable_raw_asset(): void
    {
        $this->travelTo('2026-09-03 14:00:00');
        Storage::fake('atlas_raw');
        Http::preventStrayRequests();
        $this->fakeAdeme();

        $command = $this->artisan('atlas:source:acquire', ['source' => 'ADEME']);

        $command
            ->expectsOutputToContain(self::ASSET_SHA256)
            ->expectsOutputToContain('stored')
            ->expectsOutputToContain('no parsing or canonical write was performed')
            ->assertSuccessful()
            ->run();
        Storage::disk('atlas_raw')->assertExists($this->objectKey());
        $this->assertDatabaseHas('raw_assets', [
            'disk' => 'atlas_raw',
            'object_key' => $this->objectKey(),
            'sha256' => self::ASSET_SHA256,
            'file_size' => 15,
        ]);
        $this->assertDatabaseHas('ingestion_runs', [
            'phase' => 'acquire_raw',
            'status' => 'completed',
        ]);
        Http::assertSentCount(3);
    }

    public function test_reuses_the_existing_raw_asset_for_the_same_release(): void
    {
        $this->travelTo('2026-09-03 14:00:00');
        Storage::fake('atlas_raw');
        Http::preventStrayRequests();
        $this->fakeAdeme();

        $this->artisan('atlas:source:acquire', ['source' => 'ADEME'])
            ->assertSuccessful()
            ->run();
        $command = $this->artisan('atlas:source:acquire', ['source' => 'ADEME']);

        $command
            ->expectsOutputToContain('already stored')
            ->assertSuccessful()
            ->run();
        $this->assertDatabaseCount('source_releases', 1);
        $this->assertDatabaseCount('ingestion_runs', 1);
        $this->assertDatabaseCount('raw_assets', 1);
        Http::assertSentCount(5);
    }

    public function test_rejects_the_download_when_the_upstream_checksum_does_not_match(): void
    {
        $this->travelTo('2026-09-03 14:00:00');
        Storage::fake('atlas_raw');
        Http::preventStrayRequests();
        $this->fakeAdeme('00000000000000000000000000000000');

        $command = $this->artisan('atlas:source:acquire', ['source' => 'ADEME']);

        $command
            ->expectsOutputToContain('ADEME upstream MD5 verification failed.')
            ->assertExitCode(2)
            ->run();
        Storage::disk('atlas_raw')->assertMissing($this->objectKey());
        $this->assertDatabaseCount('raw_assets', 0);
        $this->assertDatabaseHas('ingestion_runs', [
            'phase' => 'acquire_raw',
            'status' => 'failed',
            'failure_code' => 'SourceContractViolation',
        ]);
        Http::assertSentCount(3);
    }

    private function fakeAdeme(string $md5 = self::ASSET_MD5): void
    {
        Http::fake([
            self::DATASET_URL => Http::response([
                'id' => 'base-carboner',
                'status' => 'finalized',
                'count' => 18616,
                'dataUpdatedAt' => '2025-07-03T12:00:00.000Z',
                'file' => [
                    'name' => 'Base_Carbone_V23.6.csv',
                    'size' => 15,
                    'md5' => $md5,
                ],
                'license' => [
                    'title' => 'Licence Ouverte / Open Licence version 2.0',
                ],
            ]),
            self::DATASET_URL.'/data-files' => Http::response([
                [
                    'key' => 'original',
                    'name' => 'Base_Carbone_V23.6.csv',
                    'url' => self::ASSET_URL,
                ],
            ]),
            self::ASSET_URL => Http::response(
                self::ASSET_BODY,
                headers: ['Content-Type' => 'text/csv'],
            ),
        ]);
    }

    private function objectKey(): string
    {
        return 'sources/ademe/2026/09/03/'.self::ASSET_SHA256.'/Base_Carbone_V23.6.csv';
    }
}
