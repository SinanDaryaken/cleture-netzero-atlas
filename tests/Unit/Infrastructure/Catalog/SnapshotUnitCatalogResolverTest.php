<?php

namespace Tests\Unit\Infrastructure\Catalog;

use App\Application\Contracts\CatalogSnapshotLoader;
use App\Domain\Catalog\CatalogResolutionStatus;
use App\Domain\Catalog\CatalogSnapshot;
use App\Domain\Catalog\CatalogSnapshotDescriptor;
use App\Domain\Catalog\CatalogType;
use App\Infrastructure\Catalog\SnapshotUnitCatalogResolver;
use Tests\TestCase;

final class SnapshotUnitCatalogResolverTest extends TestCase
{
    public function test_proposes_one_definition_for_an_exact_unit_code_or_symbol(): void
    {
        $resolver = new SnapshotUnitCatalogResolver($this->loader());

        $resolution = $resolver->resolve('kg');

        $this->assertSame(CatalogResolutionStatus::Proposed, $resolution->status);
        $this->assertSame('01a00000-0000-7000-8000-000000000001', $resolution->target['canonical_id']);
        $this->assertSame('unit-catalog-v1', $resolution->target['catalog_version']);
        $this->assertSame(['unit_code', 'unit_symbol'], $resolution->matchedBy);
    }

    public function test_keeps_an_unsupported_compound_ademe_unit_unresolved(): void
    {
        $resolver = new SnapshotUnitCatalogResolver($this->loader());

        $resolution = $resolver->resolve('kgCO2e/kWh');

        $this->assertSame(CatalogResolutionStatus::Unresolved, $resolution->status);
        $this->assertNull($resolution->target);
        $this->assertSame([], $resolution->candidateIds);
    }

    private function loader(): CatalogSnapshotLoader
    {
        $sha256 = str_repeat('b', 64);
        $snapshot = new CatalogSnapshot(
            new CatalogSnapshotDescriptor(
                catalog: CatalogType::Unit,
                schemaVersion: 'atlas-catalog-snapshot/v1',
                owner: 'NetZeroAdmin',
                version: 'unit-catalog-v1',
                contentSchemaVersion: 'unit-catalog-release/v1',
                canonicalization: 'netzero-sorted-json-v1',
                sha256: $sha256,
                sizeBytes: 1,
                artifactPath: "atlas-catalog-snapshots/unit/sha256/{$sha256}.json",
            ),
            [
                'schema_version' => 'unit-catalog-release/v1',
                'release' => [
                    'id' => '01a00000-0000-7000-8000-000000000010',
                    'version' => 'unit-catalog-v1',
                ],
                'definitions' => [[
                    'id' => '01a00000-0000-7000-8000-000000000001',
                    'unit_code' => 'kg',
                    'unit_symbol' => 'kg',
                ]],
                'conversions' => [],
            ],
        );

        return new class($snapshot) implements CatalogSnapshotLoader
        {
            public function __construct(private readonly CatalogSnapshot $snapshot) {}

            public function load(CatalogType $catalog): CatalogSnapshot
            {
                if ($catalog !== CatalogType::Unit) {
                    throw new \LogicException('Unexpected catalog.');
                }

                return $this->snapshot;
            }
        };
    }
}
