<?php

namespace Tests\Unit\Infrastructure\Catalog;

use App\Application\Contracts\CatalogSnapshotLoader;
use App\Domain\Catalog\CatalogResolutionStatus;
use App\Domain\Catalog\CatalogSnapshot;
use App\Domain\Catalog\CatalogSnapshotDescriptor;
use App\Domain\Catalog\CatalogType;
use App\Infrastructure\Catalog\SnapshotGeographyCatalogResolver;
use Tests\TestCase;

final class SnapshotGeographyCatalogResolverTest extends TestCase
{
    public function test_proposes_one_usable_country_for_an_exact_code_or_name(): void
    {
        $resolver = new SnapshotGeographyCatalogResolver($this->loader([
            $this->country('01a00000-0000-7000-8000-000000000001', 'FR', 'FRA', '250', 'France'),
        ]));

        $byCode = $resolver->resolveCountry('fr', null);
        $byName = $resolver->resolveCountry(null, 'france');

        $this->assertSame(CatalogResolutionStatus::Proposed, $byCode->status);
        $this->assertSame('01a00000-0000-7000-8000-000000000001', $byCode->target['canonical_geography_id']);
        $this->assertSame('NetZeroAdmin', $byCode->target['owner']);
        $this->assertSame(['code'], $byCode->matchedBy);
        $this->assertSame(CatalogResolutionStatus::Proposed, $byName->status);
        $this->assertSame(['name:fr'], $byName->matchedBy);
    }

    public function test_keeps_a_source_specific_or_missing_country_label_unresolved(): void
    {
        $resolver = new SnapshotGeographyCatalogResolver($this->loader([
            $this->country('01a00000-0000-7000-8000-000000000001', 'FR', 'FRA', '250', 'France'),
        ]));

        $resolution = $resolver->resolveCountry(null, 'France continentale');

        $this->assertSame(CatalogResolutionStatus::Unresolved, $resolution->status);
        $this->assertNull($resolution->target);
        $this->assertSame([], $resolution->candidateIds);
    }

    public function test_marks_a_shared_exact_name_as_ambiguous_without_selecting_a_country(): void
    {
        $resolver = new SnapshotGeographyCatalogResolver($this->loader([
            $this->country('01a00000-0000-7000-8000-000000000001', 'AA', 'AAA', '001', 'Shared'),
            $this->country('01a00000-0000-7000-8000-000000000002', 'BB', 'BBB', '002', 'Shared'),
        ]));

        $resolution = $resolver->resolveCountry(null, 'Shared');

        $this->assertSame(CatalogResolutionStatus::Ambiguous, $resolution->status);
        $this->assertNull($resolution->target);
        $this->assertCount(2, $resolution->candidateIds);
    }

    /** @param list<array<string, mixed>> $countries */
    private function loader(array $countries): CatalogSnapshotLoader
    {
        $sha256 = str_repeat('a', 64);
        $snapshot = new CatalogSnapshot(
            new CatalogSnapshotDescriptor(
                catalog: CatalogType::Geography,
                schemaVersion: 'atlas-catalog-snapshot/v1',
                owner: 'NetZeroAdmin',
                version: "sha256:{$sha256}",
                contentSchemaVersion: 'netzero-geography-snapshot/v1',
                canonicalization: 'netzero-sorted-json-v1',
                sha256: $sha256,
                sizeBytes: 1,
                artifactPath: "atlas-catalog-snapshots/geography/sha256/{$sha256}.json",
            ),
            [
                'schema_version' => 'netzero-geography-snapshot/v1',
                'owner' => 'NetZeroAdmin',
                'countries' => $countries,
                'provinces' => [],
                'districts' => [],
            ],
        );

        return new class($snapshot) implements CatalogSnapshotLoader
        {
            public function __construct(private readonly CatalogSnapshot $snapshot) {}

            public function load(CatalogType $catalog): CatalogSnapshot
            {
                if ($catalog !== CatalogType::Geography) {
                    throw new \LogicException('Unexpected catalog.');
                }

                return $this->snapshot;
            }
        };
    }

    /** @return array<string, mixed> */
    private function country(string $id, string $iso2, string $iso3, string $numeric, string $name): array
    {
        return [
            'id' => $id,
            'active' => true,
            'deleted' => false,
            'usable' => true,
            'iso2' => $iso2,
            'iso3' => $iso3,
            'numeric_code' => $numeric,
            'names' => [[
                'language_id' => '01a00000-0000-7000-8000-000000000010',
                'language_code' => 'fr',
                'language_usable' => true,
                'name' => $name,
            ]],
        ];
    }
}
