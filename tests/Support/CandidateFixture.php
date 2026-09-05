<?php

namespace Tests\Support;

use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Catalog\CatalogSnapshot;
use App\Domain\Catalog\CatalogSnapshotDescriptor;
use App\Domain\Catalog\CatalogType;

final class CandidateFixture
{
    public const UNIT_ID = '01a00000-0000-7000-8000-000000000001';

    public const GEO_ID = '01a00000-0000-7000-8000-000000000002';

    public static function draft(string $key = 'test:factor:release:1', string $value = '1.25'): CandidateEntityDraft
    {
        $provenance = $key.':provenance';
        $unit = $key.':unit';
        $methodology = $key.':methodology';
        $quantity = ['value_state' => 'known', 'value' => $value, 'value_reason_code' => null, 'source_precision' => null,
            'output_unit' => ['raw_code' => 'kg', 'raw_label' => 'kg', 'mapping_proposal_key' => $unit],
            'activity_unit' => null, 'basis_qualifiers' => [], 'provenance_refs' => [$provenance]];
        $mapping = [];
        foreach (['unit' => 'kg', 'taxonomy' => 'source-category', 'intended_use' => null] as $domain => $sourceValue) {
            $mapping[] = ['proposal_key' => $key.':'.$domain, 'domain' => $domain, 'source_value' => $sourceValue,
                'status' => 'unresolved', 'target' => null, 'confidence' => null, 'ruleset_version' => 'source-test-v1',
                'evidence_refs' => [$key.':evidence'], 'provenance_refs' => [$provenance]];
        }

        return new CandidateEntityDraft('2.0.0', $key, 'test:factor', 'default', 'co2e_total', ['source_unspecified'],
            [['locale' => 'en', 'label' => 'Test factor', 'description' => null]],
            [['scheme' => 'TEST', 'code' => 'category', 'label' => null, 'path' => [], 'provenance_refs' => [$provenance]]],
            $key.':component', $quantity,
            [['component_key' => $key.':component', 'value_kind' => 'co2e_total', 'basis' => 'source_total', 'gas_code' => null,
                'quantity' => $quantity, 'methodology_ref' => $methodology, 'provenance_refs' => [$provenance]]],
            ['reference_period' => ['kind' => 'year', 'year' => 2024, 'start' => null, 'end' => null, 'label' => null],
                'validity' => ['valid_from' => '2024-01-01', 'valid_to' => null], 'source_published_at' => '2025-01-01T00:00:00Z',
                'retrieved_at' => '2026-01-01T00:00:00Z', 'provenance_refs' => [$provenance]],
            ['methodology_key' => $methodology, 'methodology_code' => null, 'methodology_version' => null, 'boundary_code' => null,
                'lifecycle_stage_codes' => [], 'scenario_code' => null, 'gwp' => null, 'formula_or_recipe_ref' => null, 'provenance_refs' => [$provenance]],
            [['proposal_key' => $key.':geography', 'role' => 'market', 'raw_code' => 'TR', 'raw_label' => 'Türkiye',
                'status' => 'unresolved', 'target' => null, 'confidence' => null, 'evidence_refs' => [$key.':evidence'], 'provenance_refs' => [$provenance]]],
            $mapping, [], [],
            [['evidence_key' => $key.':evidence', 'kind' => 'source_row', 'summary' => 'Test source row', 'source_reference' => 'row:2', 'provenance_refs' => [$provenance]]],
            [['provenance_key' => $provenance, 'field_pointers' => ['/primary_quantity/value'], 'source_asset_key' => 'sources/test/raw.csv',
                'source_asset_sha256' => hash('sha256', 'test raw'), 'locator' => ['kind' => 'csv_cell', 'file_path' => 'sources/test/raw.csv',
                    'sheet' => null, 'table' => null, 'row' => 2, 'column' => 1, 'cell' => null, 'json_pointer' => null, 'byte_start' => null, 'byte_end' => null],
                'raw_value' => $value, 'transform_chain' => [['operation' => 'test_normalization', 'version' => '1.0.0']]]], []);
    }

    public static function payload(CatalogType $type): array
    {
        if ($type === CatalogType::Geography) {
            return ['schema_version' => 'netzero-geography-snapshot/v1', 'owner' => 'NetZeroAdmin',
                'countries' => [['id' => self::GEO_ID, 'active' => true, 'deleted' => false, 'usable' => true,
                    'iso2' => 'TR', 'iso3' => 'TUR', 'numeric_code' => '792',
                    'names' => [['language_id' => '01a00000-0000-7000-8000-000000000003', 'language_code' => 'tr', 'language_usable' => true, 'name' => 'Türkiye']]]],
                'provinces' => [], 'districts' => []];
        }

        return ['schema_version' => 'unit-catalog-release/v1', 'release' => ['id' => '01a00000-0000-7000-8000-000000000004', 'version' => 'test-unit-v1'],
            'definitions' => [['id' => self::UNIT_ID, 'unit_type_id' => self::UNIT_ID, 'unit_dimension_id' => self::UNIT_ID,
                'unit_code' => 'kg', 'unit_symbol' => 'kg', 'dimension_code' => 'mass', 'transform_kind' => 'ratio', 'is_base' => true,
                'scale' => ['numerator' => '1', 'denominator' => '1'], 'offset' => ['numerator' => '0', 'denominator' => '1'], 'sha256' => str_repeat('a', 64)]], 'conversions' => []];
    }

    public static function snapshot(CatalogType $type): CatalogSnapshot
    {
        $payload = self::payload($type);
        $bytes = json_encode($payload, JSON_THROW_ON_ERROR);
        $hash = hash('sha256', $bytes);

        return new CatalogSnapshot(new CatalogSnapshotDescriptor($type, 'atlas-catalog-snapshot/v1', 'NetZeroAdmin',
            $type === CatalogType::Unit ? 'test-unit-v1' : 'sha256:'.$hash, $payload['schema_version'], 'netzero-sorted-json-v1',
            $hash, strlen($bytes), "atlas-catalog-snapshots/{$type->value}/sha256/{$hash}.json"), $payload);
    }
}
