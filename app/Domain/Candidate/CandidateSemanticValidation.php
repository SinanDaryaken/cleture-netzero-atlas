<?php

namespace App\Domain\Candidate;

use App\Domain\Catalog\CatalogSnapshot;
use DateTimeImmutable;

final readonly class CandidateSemanticValidation
{
    public function __construct(private CandidateRecordReferences $references) {}

    /** @return list<CandidateFinding> */
    public function inspect(array $record, CandidateValidationRuleset $rules, CatalogSnapshot $unit, CatalogSnapshot $geography, array $rawAssets): array
    {
        $findings = [];
        $key = $record['candidate_key'];
        $add = static function (string $code, string $pointer, array $evidence = [], array $context = []) use (&$findings, $rules, $key): void {
            $findings[] = $rules->finding($code, $key, $pointer, $evidence, $context);
        };
        foreach ($this->references->inspect($record) as $pointer) {
            $add('reference_invalid', $pointer);
        }
        $this->provenance($record, $rawAssets, $add);
        $this->mappings($record, $rules, $unit, $geography, $add);
        $this->temporal($record['temporal'], $add);

        foreach ($record['components'] as $component) {
            if ($component['component_key'] === $record['primary_component_key'] && $component['quantity'] !== $record['primary_quantity']) {
                $add('primary_component_mismatch', '/primary_quantity');
            }
        }
        if ($record['primary_quantity']['value_state'] !== 'known') {
            $add('primary_value_missing', '/primary_quantity/value');
        } elseif (str_starts_with($record['primary_quantity']['value'], '-')) {
            $add('negative_value_review', '/primary_quantity/value');
        }
        if ($record['methodology']['formula_or_recipe_ref'] !== null) {
            $add('formula_unverified', '/methodology/formula_or_recipe_ref');
        }

        return $findings;
    }

    private function provenance(array $record, array $rawAssets, \Closure $add): void
    {
        $assets = [];
        foreach ($rawAssets as $asset) {
            $assets[$asset['asset_key']] = $asset['sha256'];
        }
        foreach ($record['provenance'] as $index => $provenance) {
            $pointer = "/provenance/{$index}";
            if (($assets[$provenance['source_asset_key']] ?? null) !== $provenance['source_asset_sha256']) {
                $add('provenance_invalid', $pointer.'/source_asset_sha256');
            }
            foreach ($provenance['field_pointers'] as $field) {
                if (! $this->references->pointerExists($record, $field)) {
                    $add('provenance_invalid', $pointer.'/field_pointers');
                } elseif ($field === '') {
                    $add('provenance_coarse', $pointer.'/field_pointers');
                }
            }
            $locator = $provenance['locator'];
            $valid = $locator['file_path'] === $provenance['source_asset_key'] && match ($locator['kind']) {
                'csv_cell' => is_int($locator['row']) && $locator['row'] > 0,
                'xlsx_cell' => $locator['sheet'] !== null && ($locator['cell'] !== null || ($locator['row'] !== null && $locator['column'] !== null)),
                'json_pointer' => $locator['json_pointer'] !== null,
                'byte_range' => is_int($locator['byte_start']) && is_int($locator['byte_end']) && $locator['byte_start'] <= $locator['byte_end'],
                'document_field' => $locator['column'] !== null || $locator['json_pointer'] !== null,
            };
            if (! $valid) {
                $add('provenance_invalid', $pointer.'/locator');
            }
        }
    }

    private function mappings(array $record, CandidateValidationRuleset $rules, CatalogSnapshot $unit, CatalogSnapshot $geography, \Closure $add): void
    {
        $units = array_column($unit->payload['definitions'], null, 'id');
        $geographies = [];
        foreach (['countries' => 'country', 'provinces' => 'province', 'districts' => 'district'] as $field => $level) {
            foreach ($geography->payload[$field] as $item) {
                $geographies[$item['id']] = [...$item, 'entity_level' => $level];
            }
        }
        foreach (['canonical_mapping_proposals' => ['domain', $rules->document['required_mapping_domains']], 'geography_proposals' => ['role', $rules->document['required_geography_roles']]] as $field => [$discriminator, $required]) {
            $seen = [];
            foreach ($record[$field] as $index => $proposal) {
                $pointer = "/{$field}/{$index}";
                $type = $proposal[$discriminator];
                $seen[] = $type;
                $target = $proposal['target'];
                $evidence = $proposal['evidence_refs'];
                if (($proposal['status'] === 'proposed') !== ($target !== null)) {
                    $add('mapping_invalid', $pointer.'/target', $evidence);

                    continue;
                }
                if ($target === null) {
                    if (in_array($type, $required, true)) {
                        $add('mapping_unresolved', $pointer.'/status', $evidence, ['domain' => $type, 'status' => $proposal['status']]);
                    }

                    continue;
                }
                $snapshot = $field === 'geography_proposals' ? $geography : ($type === 'unit' ? $unit : null);
                if ($snapshot === null) {
                    $add('mapping_unverifiable', $pointer.'/target', $evidence, ['domain' => $type]);

                    continue;
                }
                $id = $target['canonical_geography_id'] ?? $target['canonical_id'] ?? null;
                $definition = $field === 'geography_proposals' ? ($geographies[$id] ?? null) : ($units[$id] ?? null);
                $valid = $target['catalog_version'] === $snapshot->descriptor->version
                    && $target['catalog_sha256'] === $snapshot->descriptor->sha256 && $definition !== null;
                if ($field === 'geography_proposals') {
                    $valid = $valid && ($definition['usable'] ?? false) === true
                        && $target['owner'] === 'NetZeroAdmin' && $target['entity_level'] === $definition['entity_level'];
                } else {
                    $valid = $valid && $target['catalog'] === 'unit';
                }
                if (! $valid) {
                    $add('mapping_invalid', $pointer.'/target', $evidence);
                } elseif ($type === 'unit') {
                    // A catalog definition alone does not establish factor/applicability dimensions.
                    $add('dimension_unverified', $pointer.'/target', $evidence);
                }
            }
            foreach (array_diff($required, $seen) as $missing) {
                $add('mapping_unresolved', '/'.$field, [], ['domain' => $missing, 'status' => 'missing']);
            }
        }
    }

    private function temporal(array $temporal, \Closure $add): void
    {
        $period = $temporal['reference_period'];
        $shape = match ($period['kind']) {
            'year' => $period['year'] !== null && $period['start'] === null && $period['end'] === null && $period['label'] === null,
            'date_range' => $period['year'] === null && $period['start'] !== null && $period['end'] !== null && $period['label'] === null,
            'label' => $period['year'] === null && $period['start'] === null && $period['end'] === null && $period['label'] !== null,
            'unknown' => $period['year'] === null && $period['start'] === null && $period['end'] === null && $period['label'] === null,
        };
        if (! $shape) {
            $add('temporal_invalid', '/temporal/reference_period');
        }
        foreach ([[$period['start'], $period['end'], '/temporal/reference_period'], [$temporal['validity']['valid_from'], $temporal['validity']['valid_to'], '/temporal/validity'], [$temporal['source_published_at'], $temporal['retrieved_at'], '/temporal/source_published_at']] as [$start, $end, $pointer]) {
            if ($start !== null && $end !== null && new DateTimeImmutable($start) > new DateTimeImmutable($end)) {
                $add('temporal_invalid', $pointer);
            }
        }
        if (in_array($period['kind'], ['unknown', 'label'], true) || $temporal['validity']['valid_from'] === null) {
            $add('temporal_unknown', '/temporal');
        }
    }
}
