<?php

namespace App\Domain\Catalog;

use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use JsonException;
use stdClass;

/** netzero-sorted-json-v1; deliberately separate from candidate RFC 8785. */
final class SortedCatalogJson
{
    public function decode(string $bytes): stdClass
    {
        try {
            $value = json_decode($bytes, false, 64, JSON_THROW_ON_ERROR);
            if (! $value instanceof stdClass || $this->encode($value) !== $bytes) {
                throw new CatalogContractViolation('Expected exact sorted JSON object bytes.');
            }

            return $value;
        } catch (JsonException $exception) {
            throw new CatalogContractViolation('Invalid catalog JSON.', previous: $exception);
        }
    }

    public function encode(mixed $value): string
    {
        return json_encode($this->sort($value), JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    }

    private function sort(mixed $value): mixed
    {
        if (is_float($value)) {
            throw new CatalogContractViolation('Binary floating point is not catalog evidence.');
        }
        if (is_object($value)) {
            $properties = get_object_vars($value);
            ksort($properties, SORT_STRING);

            return (object) array_map($this->sort(...), $properties);
        }
        if (is_array($value)) {
            if (! array_is_list($value)) {
                ksort($value, SORT_STRING);
            }

            return array_map($this->sort(...), $value);
        }

        return $value;
    }
}
