<?php

namespace Tests\Unit\Infrastructure\Catalog;

use App\Domain\Catalog\CatalogSnapshotIntegrity;
use App\Domain\Catalog\CatalogType;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use App\Infrastructure\Catalog\LaravelCatalogSnapshotLoader;
use App\Infrastructure\Contracts\OpisCatalogSchemaValidator;
use App\Infrastructure\Contracts\PinnedCatalogContractRegistry;
use Illuminate\Filesystem\FilesystemManager;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class LaravelCatalogSnapshotLoaderTest extends TestCase
{
    public function test_loads_verified_bytes_once_and_returns_the_same_immutable_snapshot(): void
    {
        Storage::fake('atlas_catalogs');
        [$loader] = $this->loader($this->geographyPayload());

        $first = $loader->load(CatalogType::Geography);
        $second = $loader->load(CatalogType::Geography);

        $this->assertSame($first, $second);
        $this->assertSame('NetZeroAdmin', $first->descriptor->owner);
        $this->assertCount(2, $first->payload['countries']);
        $this->assertSame('TR', $first->payload['countries'][1]['iso2']);
    }

    public function test_rejects_payload_bytes_that_no_longer_match_the_descriptor(): void
    {
        Storage::fake('atlas_catalogs');
        [$loader, $artifactPath] = $this->loader($this->geographyPayload());
        Storage::disk('atlas_catalogs')->put($artifactPath, '{}');

        $this->expectException(CatalogContractViolation::class);
        $this->expectExceptionMessage('catalog payload identity does not match its descriptor');

        $loader->load(CatalogType::Geography);
    }

    public function test_rejects_a_geography_descriptor_version_that_does_not_pin_its_payload(): void
    {
        Storage::fake('atlas_catalogs');
        [$loader] = $this->loader($this->geographyPayload(), [
            'version' => 'sha256:'.str_repeat('b', 64),
        ]);

        $this->expectException(CatalogContractViolation::class);
        $this->expectExceptionMessage('Catalog descriptor identity is invalid.');

        $loader->load(CatalogType::Geography);
    }

    public function test_rejects_a_geography_record_with_an_unknown_parent(): void
    {
        Storage::fake('atlas_catalogs');
        $payload = $this->geographyPayload();
        $payload['provinces'][0]['country_id'] = '01a00000-0000-7000-8000-000000000099';
        [$loader] = $this->loader($payload);

        $this->expectException(CatalogContractViolation::class);
        $this->expectExceptionMessage('references an unknown country');

        $loader->load(CatalogType::Geography);
    }

    /**
     * @param  array<string, mixed>  $payload
     * @param  array<string, mixed>  $descriptorOverrides
     * @return array{LaravelCatalogSnapshotLoader, string}
     */
    private function loader(array $payload, array $descriptorOverrides = []): array
    {
        $payloadBytes = json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);
        $payloadSha256 = hash('sha256', $payloadBytes);
        $artifactPath = "atlas-catalog-snapshots/geography/sha256/{$payloadSha256}.json";
        $descriptor = array_replace([
            'schema_version' => 'atlas-catalog-snapshot/v1',
            'owner' => 'NetZeroAdmin',
            'catalog' => 'geography',
            'version' => "sha256:{$payloadSha256}",
            'content_schema_version' => 'netzero-geography-snapshot/v1',
            'canonicalization' => 'netzero-sorted-json-v1',
            'sha256' => $payloadSha256,
            'size_bytes' => strlen($payloadBytes),
            'artifact_path' => $artifactPath,
        ], $descriptorOverrides);
        $descriptorBytes = json_encode($descriptor, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);
        $descriptorPath = $artifactPath.'.manifest.json';
        Storage::disk('atlas_catalogs')->put($artifactPath, $payloadBytes);
        Storage::disk('atlas_catalogs')->put($descriptorPath, $descriptorBytes);
        $contracts = new PinnedCatalogContractRegistry(
            base_path('resources/contracts/netzero-admin/catalog-v1/contract-manifest.json'),
        );

        return [
            new LaravelCatalogSnapshotLoader(
                filesystems: app(FilesystemManager::class),
                schemaValidator: new OpisCatalogSchemaValidator($contracts),
                integrity: new CatalogSnapshotIntegrity,
                disk: 'atlas_catalogs',
                snapshotConfigurations: [
                    'geography' => [
                        'descriptor_path' => $descriptorPath,
                        'descriptor_sha256' => hash('sha256', $descriptorBytes),
                    ],
                ],
            ),
            $artifactPath,
        ];
    }

    /** @return array<string, mixed> */
    private function geographyPayload(): array
    {
        $franceId = '01a00000-0000-7000-8000-000000000001';
        $turkiyeId = '01a00000-0000-7000-8000-000000000002';
        $provinceId = '01a00000-0000-7000-8000-000000000003';

        return [
            'schema_version' => 'netzero-geography-snapshot/v1',
            'owner' => 'NetZeroAdmin',
            'countries' => [
                [
                    'id' => $franceId,
                    'active' => true,
                    'deleted' => false,
                    'usable' => true,
                    'iso2' => 'FR',
                    'iso3' => 'FRA',
                    'numeric_code' => '250',
                    'names' => [[
                        'language_id' => '01a00000-0000-7000-8000-000000000010',
                        'language_code' => 'fr',
                        'language_usable' => true,
                        'name' => 'France',
                    ]],
                ],
                [
                    'id' => $turkiyeId,
                    'active' => true,
                    'deleted' => false,
                    'usable' => true,
                    'iso2' => 'TR',
                    'iso3' => 'TUR',
                    'numeric_code' => '792',
                    'names' => [[
                        'language_id' => '01a00000-0000-7000-8000-000000000011',
                        'language_code' => 'tr',
                        'language_usable' => true,
                        'name' => 'Türkiye',
                    ]],
                ],
            ],
            'provinces' => [[
                'id' => $provinceId,
                'active' => true,
                'deleted' => false,
                'usable' => true,
                'country_id' => $turkiyeId,
                'name' => 'Ankara',
            ]],
            'districts' => [[
                'id' => '01a00000-0000-7000-8000-000000000004',
                'active' => true,
                'deleted' => false,
                'usable' => true,
                'province_id' => $provinceId,
                'name' => 'Çankaya',
            ]],
        ];
    }
}
