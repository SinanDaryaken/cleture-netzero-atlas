<?php

namespace App\Domain\Catalog;

use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use Brick\Math\BigRational;

final readonly class DeliveryCatalogIntegrity
{
    public function __construct(private SortedCatalogJson $json, private CatalogSnapshotIntegrity $legacy) {}

    public function assertValid(CatalogSnapshot $snapshot): void
    {
        $type = $snapshot->descriptor->catalog;
        if (in_array($type, [CatalogType::Unit, CatalogType::Geography], true)) {
            $this->legacy->assertValid($snapshot);
        }
        match ($type) {
            CatalogType::Unit => $this->unit($snapshot->payload),
            CatalogType::Currency => $this->currency($snapshot->payload),
            CatalogType::Taxonomy, CatalogType::IntendedUse => $this->review($snapshot->payload, $type),
            default => null,
        };
    }

    private function unit(array $payload): void
    {
        $definitions = $this->index($payload['definitions'], 'id');
        $dimensions = $this->index($payload['reference']['physical_dimensions'], 'id');
        $mappings = $this->index($payload['reference']['quantity_kind_mappings'], 'quantity_kind_id');
        $units = [];
        $pairs = [];
        $bases = [];
        foreach ($definitions as $definition) {
            $scientific = $definition['scientific'];
            $unit = $scientific['unit_definition'];
            $kind = $definition['quantity_kind_id'];
            $mapping = $mappings[$kind] ?? null;
            $dimension = $dimensions[$unit['dimension_id']] ?? null;
            $pair = $kind.':'.$definition['unit_type_id'];
            if (isset($pairs[$pair]) || $definition['unit_dimension_id'] !== $kind
                || $mapping === null || $mapping['reference_kind_id'] !== $scientific['reference_kind_id']
                || $mapping['code'] !== $definition['dimension_code']
                || $scientific['reference_sha256'] !== $payload['reference']['sha256']
                || $dimension !== $scientific['physical_dimension'] || $unit['dimension_code'] !== $dimension['code']
                || $unit['id'] !== $definition['unit_type_id'] || $unit['code'] !== $definition['unit_code']
                || $unit['symbol'] !== $definition['unit_symbol']) {
                throw new CatalogContractViolation('Scientific definition/reference relationship mismatch.');
            }
            if (isset($units[$unit['id']]) && $units[$unit['id']]['unit'] !== $unit) {
                throw new CatalogContractViolation('Conflicting scientific unit definitions.');
            }
            $units[$unit['id']] = ['unit' => $unit, 'terms' => $scientific['terms']];
            $pairs[$pair] = true;
            $scale = $this->fraction($definition['scale']);
            $offset = $this->fraction($definition['offset']);
            if (! $scale->isPositive() || ($definition['is_base'] && (! $scale->isEqualTo(1) || ! $offset->isZero()))) {
                throw new CatalogContractViolation('Invalid exact unit scale or base.');
            }
            if ($definition['is_base']) {
                $bases[$kind] = ($bases[$kind] ?? 0) + 1;
            }
            $hashInput = $definition;
            unset($hashInput['id'], $hashInput['quantity_kind_id'], $hashInput['sha256']);
            $hashInput['release_id'] = $payload['release']['id'];
            $this->hash($definition['sha256'], $hashInput);
        }
        foreach ($mappings as $kind => $mapping) {
            if (($bases[$kind] ?? 0) !== 1) {
                throw new CatalogContractViolation('Each delivered quantity kind requires one base definition.');
            }
        }
        foreach ($units as $unitId => $entry) {
            $positions = [];
            foreach ($entry['terms'] as $term) {
                if ($term['unit_id'] !== $unitId || ! isset($units[$term['component_unit_id']])
                    || isset($positions[$term['position']])) {
                    throw new CatalogContractViolation('Scientific expression has a missing or conflicting component.');
                }
                $positions[$term['position']] = true;
            }
        }
        foreach ($payload['reference']['aliases'] as $alias) {
            if (! isset($units[$alias['unit_id']])) {
                throw new CatalogContractViolation('Alias references an unknown scientific unit.');
            }
        }
        foreach ($payload['conversions'] as $conversion) {
            $from = $definitions[$conversion['from_definition_id']];
            $to = $definitions[$conversion['to_definition_id']];
            $multiplier = $this->fraction($conversion['multiplier']);
            $offset = $this->fraction($conversion['offset']);
            if ($from['quantity_kind_id'] !== $to['quantity_kind_id']
                || ! $multiplier->isEqualTo($this->fraction($from['scale'])->dividedBy($this->fraction($to['scale'])))
                || ! $offset->isEqualTo($this->fraction($from['offset'])->minus($this->fraction($to['offset']))->dividedBy($this->fraction($to['scale'])))) {
                throw new CatalogContractViolation('Conversion does not match exact same-kind definitions.');
            }
            $this->hash($conversion['sha256'], ['release_id' => $payload['release']['id'],
                'from_definition_sha256' => $from['sha256'], 'to_definition_sha256' => $to['sha256'],
                'multiplier' => $conversion['multiplier'], 'offset' => $conversion['offset']]);
        }
    }

    private function fraction(array $value): BigRational
    {
        $fraction = BigRational::ofFraction($value['numerator'], $value['denominator']);
        if ((string) $fraction->getNumerator() !== $value['numerator'] || (string) $fraction->getDenominator() !== $value['denominator']) {
            throw new CatalogContractViolation('Non-reduced rational catalog value.');
        }

        return $fraction;
    }

    private function currency(array $payload): void
    {
        $entries = $this->index($payload['currencies'], 'id');
        $this->index($payload['currencies'], 'code');
        foreach ($entries as $entry) {
            $this->entryHash($entry);
            if ($entry['usable'] !== ($entry['active'] && ! $entry['deleted'])) {
                throw new CatalogContractViolation('Currency lifecycle mismatch.');
            }
        }
    }

    private function review(array $payload, CatalogType $type): void
    {
        $entries = $this->index($payload[$type === CatalogType::Taxonomy ? 'nodes' : 'uses'], 'canonical_id');
        foreach ($entries as $entry) {
            $this->entryHash($entry);
            if ($type === CatalogType::IntendedUse) {
                continue;
            }
            if ($entry['canonical_id'] !== $entry['kind'].':'.$entry['id']) {
                throw new CatalogContractViolation('Taxonomy typed identity mismatch.');
            }
            $expected = match ($entry['kind']) {
                'segment' => ['protocol', 'scope'], 'category' => ['segment'], 'material' => ['consumption_type'], default => [],
            };
            $actual = [];
            foreach ($entry['parents'] as $parent) {
                $actual[] = ($entries[$parent] ?? throw new CatalogContractViolation('Missing taxonomy parent.'))['kind'];
            }
            sort($actual, SORT_STRING);
            if ($actual !== $expected) {
                throw new CatalogContractViolation('Invalid taxonomy parent kinds.');
            }
            $this->index($entry['names'], 'language_id');
        }
        if ($type === CatalogType::IntendedUse) {
            $ids = array_keys($entries);
            sort($ids, SORT_STRING);
            if ($ids !== ['corporate_carbon_footprint', 'life_cycle_assessment', 'product_carbon_footprint']) {
                throw new CatalogContractViolation('Intended-use catalog does not contain the three contracted identities.');
            }

            return;
        }
        $links = $this->index($payload['category_consumption_links'], 'id');
        $pairs = [];
        foreach ($links as $link) {
            $this->entryHash($link);
            $pair = $link['category_id'].':'.$link['consumption_type_id'];
            if (! isset($entries['category:'.$link['category_id']], $entries['consumption_type:'.$link['consumption_type_id']])
                || (! $link['deleted'] && isset($pairs[$pair]))) {
                throw new CatalogContractViolation('Taxonomy assignment mismatch.');
            }
            if (! $link['deleted']) {
                $pairs[$pair] = true;
            }
        }
    }

    private function index(array $entries, string $key): array
    {
        $result = [];
        foreach ($entries as $entry) {
            if (isset($result[$entry[$key]])) {
                throw new CatalogContractViolation('Duplicate catalog identity: '.$key);
            }
            $result[$entry[$key]] = $entry;
        }

        return $result;
    }

    private function entryHash(array $entry): void
    {
        $hash = $entry['sha256'];
        unset($entry['sha256']);
        $this->hash($hash, $entry);
    }

    private function hash(string $hash, array $value): void
    {
        if (! hash_equals($hash, hash('sha256', $this->json->encode($value)))) {
            throw new CatalogContractViolation('Catalog entry hash mismatch.');
        }
    }
}
