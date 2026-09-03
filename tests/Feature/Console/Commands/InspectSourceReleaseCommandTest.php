<?php

namespace Tests\Feature\Console\Commands;

use Illuminate\Support\Facades\Http;
use Tests\TestCase;

final class InspectSourceReleaseCommandTest extends TestCase
{
    private const DATASET_URL = 'https://data.ademe.fr/data-fair/api/v1/datasets/base-carboner';

    public function test_reports_the_ademe_release_without_persisting_source_data(): void
    {
        Http::preventStrayRequests();
        Http::fake([
            self::DATASET_URL => Http::response($this->metadata()),
            self::DATASET_URL.'/data-files' => Http::response([
                [
                    'key' => 'original',
                    'name' => 'Base_Carbone_V23.6.csv',
                    'url' => self::DATASET_URL.'/data-files/Base_Carbone_V23.6.csv',
                ],
            ]),
        ]);

        $command = $this->artisan('atlas:source:inspect', ['source' => 'ademe']);

        $command
            ->expectsOutputToContain('ADEME')
            ->expectsOutputToContain('23.6')
            ->expectsOutputToContain('18,616')
            ->expectsOutputToContain('f234de9bb2cadc671c8337dc99d674f5ea9e24b7b254ef29691661b75890c3ed')
            ->expectsOutputToContain('Inspection completed without downloading or persisting source data.')
            ->assertSuccessful()
            ->run();
        Http::assertSentCount(2);
    }

    public function test_rejects_the_release_when_the_open_license_contract_changes(): void
    {
        Http::preventStrayRequests();
        Http::fake([
            self::DATASET_URL => Http::response($this->metadata([
                'license' => ['title' => 'Unknown license'],
            ])),
        ]);

        $command = $this->artisan('atlas:source:inspect', ['source' => 'ADEME']);

        $command
            ->expectsOutputToContain('ADEME open-license contract changed.')
            ->assertExitCode(2)
            ->run();
        Http::assertSentCount(1);
    }

    public function test_rejects_an_unknown_source_without_an_http_request(): void
    {
        Http::preventStrayRequests();

        $command = $this->artisan('atlas:source:inspect', ['source' => 'unknown']);

        $command
            ->expectsOutputToContain('Unknown source adapter: unknown')
            ->assertExitCode(2)
            ->run();
        Http::assertNothingSent();
    }

    /**
     * @param  array<string, mixed>  $overrides
     * @return array<string, mixed>
     */
    private function metadata(array $overrides = []): array
    {
        return array_replace_recursive([
            'id' => 'base-carboner',
            'status' => 'finalized',
            'count' => 18616,
            'dataUpdatedAt' => '2025-07-03T12:00:00.000Z',
            'file' => [
                'name' => 'Base_Carbone_V23.6.csv',
                'size' => 10761452,
                'md5' => '0123456789abcdef0123456789abcdef',
            ],
            'license' => [
                'title' => 'Licence Ouverte / Open Licence version 2.0',
            ],
        ], $overrides);
    }
}
