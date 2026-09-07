<?php

namespace App\Domain\Catalog;

use App\Domain\Catalog\Exceptions\CatalogContractViolation;

final class CatalogSnapshotIntegrity
{
    public function assertValid(CatalogSnapshot $snapshot): void
    {
        match ($snapshot->descriptor->catalog) {
            CatalogType::Geography => $this->assertGeography($snapshot),
            CatalogType::Unit => $this->assertUnit($snapshot),
            default => throw new CatalogContractViolation('Review catalogs require delivery semantic validation.'),
        };
    }

    private function assertGeography(CatalogSnapshot $snapshot): void
    {
        $countries = $this->records($snapshot->payload, 'countries');
        $provinces = $this->records($snapshot->payload, 'provinces');
        $districts = $this->records($snapshot->payload, 'districts');
        $countryUsability = $this->usabilityById($countries, 'country');
        $provinceUsability = [];
        $districtIds = [];

        if (! in_array(true, $countryUsability, true)) {
            throw new CatalogContractViolation('Geography snapshot contains no usable country.');
        }

        $this->assertUniqueField($countries, 'iso2', 'country ISO2');
        $this->assertUniqueField($countries, 'iso3', 'country ISO3');
        $this->assertUniqueField($countries, 'numeric_code', 'country numeric code');
        $this->assertSortedById($countries, 'countries');
        $this->assertSortedById($provinces, 'provinces');
        $this->assertSortedById($districts, 'districts');

        foreach ($provinces as $province) {
            $countryId = $this->stringField($province, 'country_id', 'province');
            $id = $this->stringField($province, 'id', 'province');

            if (! array_key_exists($countryId, $countryUsability)) {
                throw new CatalogContractViolation("Geography province {$id} references an unknown country.");
            }

            $expectedUsable = ($province['active'] ?? null) === true
                && ($province['deleted'] ?? null) === false
                && $countryUsability[$countryId];

            if (($province['usable'] ?? null) !== $expectedUsable) {
                throw new CatalogContractViolation("Geography province {$id} has inconsistent usability.");
            }

            if (isset($provinceUsability[$id])) {
                throw new CatalogContractViolation("Geography snapshot contains duplicate province id {$id}.");
            }

            $provinceUsability[$id] = $expectedUsable;
        }

        foreach ($districts as $district) {
            $provinceId = $this->stringField($district, 'province_id', 'district');
            $id = $this->stringField($district, 'id', 'district');

            if (isset($districtIds[$id])) {
                throw new CatalogContractViolation("Geography snapshot contains duplicate district id {$id}.");
            }

            $districtIds[$id] = true;

            if (! array_key_exists($provinceId, $provinceUsability)) {
                throw new CatalogContractViolation("Geography district {$id} references an unknown province.");
            }

            $expectedUsable = ($district['active'] ?? null) === true
                && ($district['deleted'] ?? null) === false
                && $provinceUsability[$provinceId];

            if (($district['usable'] ?? null) !== $expectedUsable) {
                throw new CatalogContractViolation("Geography district {$id} has inconsistent usability.");
            }
        }
    }

    private function assertUnit(CatalogSnapshot $snapshot): void
    {
        $definitions = $this->records($snapshot->payload, 'definitions');
        $conversions = $this->records($snapshot->payload, 'conversions');
        $definitionsById = [];

        if (($snapshot->payload['release']['version'] ?? null) !== $snapshot->descriptor->version) {
            throw new CatalogContractViolation('Unit snapshot release version does not match its descriptor.');
        }

        if ($snapshot->descriptor->contentSchemaVersion === 'unit-catalog-release/v1') {
            $this->assertUniqueField($definitions, 'unit_code', 'unit code');
        }

        foreach ($definitions as $definition) {
            $id = $this->stringField($definition, 'id', 'unit definition');

            if (isset($definitionsById[$id])) {
                throw new CatalogContractViolation("Unit snapshot contains duplicate definition id {$id}.");
            }

            $definitionsById[$id] = $definition;
        }

        $conversionPairs = [];

        foreach ($conversions as $conversion) {
            $fromId = $this->stringField($conversion, 'from_definition_id', 'unit conversion');
            $toId = $this->stringField($conversion, 'to_definition_id', 'unit conversion');
            $pair = "{$fromId}:{$toId}";

            if (! isset($definitionsById[$fromId], $definitionsById[$toId])) {
                throw new CatalogContractViolation('Unit conversion references an unknown definition.');
            }

            if (($conversion['from_code'] ?? null) !== ($definitionsById[$fromId]['unit_code'] ?? null)
                || ($conversion['to_code'] ?? null) !== ($definitionsById[$toId]['unit_code'] ?? null)
            ) {
                throw new CatalogContractViolation('Unit conversion codes do not match their definitions.');
            }

            if (isset($conversionPairs[$pair])) {
                throw new CatalogContractViolation("Unit snapshot contains duplicate conversion pair {$pair}.");
            }

            $conversionPairs[$pair] = true;
        }
    }

    /**
     * @param  array<string, mixed>  $payload
     * @return list<array<string, mixed>>
     */
    private function records(array $payload, string $key): array
    {
        $records = $payload[$key] ?? null;

        if (! is_array($records) || ! array_is_list($records)) {
            throw new CatalogContractViolation("Catalog snapshot {$key} must be a list.");
        }

        foreach ($records as $record) {
            if (! is_array($record)) {
                throw new CatalogContractViolation("Catalog snapshot {$key} contains an invalid record.");
            }
        }

        return $records;
    }

    /**
     * @param  list<array<string, mixed>>  $records
     * @return array<string, bool>
     */
    private function usabilityById(array $records, string $label): array
    {
        $usability = [];

        foreach ($records as $record) {
            $id = $this->stringField($record, 'id', $label);
            $expectedUsable = ($record['active'] ?? null) === true && ($record['deleted'] ?? null) === false;

            if (($record['usable'] ?? null) !== $expectedUsable) {
                throw new CatalogContractViolation("Geography {$label} {$id} has inconsistent usability.");
            }

            if (isset($usability[$id])) {
                throw new CatalogContractViolation("Geography snapshot contains duplicate {$label} id {$id}.");
            }

            $usability[$id] = $expectedUsable;
        }

        return $usability;
    }

    /** @param list<array<string, mixed>> $records */
    private function assertUniqueField(array $records, string $field, string $label): void
    {
        $values = [];

        foreach ($records as $record) {
            $value = $this->stringField($record, $field, $label);

            if (isset($values[$value])) {
                throw new CatalogContractViolation("Catalog snapshot contains duplicate {$label} {$value}.");
            }

            $values[$value] = true;
        }
    }

    /** @param list<array<string, mixed>> $records */
    private function assertSortedById(array $records, string $label): void
    {
        $ids = array_map(
            fn (array $record): string => $this->stringField($record, 'id', $label),
            $records,
        );
        $sorted = $ids;
        sort($sorted, SORT_STRING);

        if ($ids !== $sorted) {
            throw new CatalogContractViolation("Geography {$label} are not in canonical id order.");
        }
    }

    /** @param array<string, mixed> $record */
    private function stringField(array $record, string $field, string $label): string
    {
        $value = $record[$field] ?? null;

        if (! is_string($value) || $value === '') {
            throw new CatalogContractViolation("Catalog {$label} has an invalid {$field}.");
        }

        return $value;
    }
}
