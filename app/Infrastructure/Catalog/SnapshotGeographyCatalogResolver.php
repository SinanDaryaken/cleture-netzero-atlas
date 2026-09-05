<?php

namespace App\Infrastructure\Catalog;

use App\Application\Contracts\CatalogSnapshotLoader;
use App\Application\Contracts\GeographyCatalogResolver;
use App\Domain\Catalog\CatalogResolution;
use App\Domain\Catalog\CatalogResolutionStatus;
use App\Domain\Catalog\CatalogType;

final readonly class SnapshotGeographyCatalogResolver implements GeographyCatalogResolver
{
    public function __construct(private CatalogSnapshotLoader $snapshots) {}

    public function resolveCountry(?string $rawCode, ?string $rawLabel): CatalogResolution
    {
        $snapshot = $this->snapshots->load(CatalogType::Geography);
        $code = $this->nonEmpty($rawCode);
        $label = $this->nonEmpty($rawLabel);
        $matches = [];

        foreach ($snapshot->payload['countries'] as $country) {
            if (($country['usable'] ?? null) !== true || ! is_string($country['id'] ?? null)) {
                continue;
            }

            $matchedBy = [];

            if ($code !== null && in_array(mb_strtoupper($code), [
                $country['iso2'] ?? null,
                $country['iso3'] ?? null,
                $country['numeric_code'] ?? null,
            ], true)) {
                $matchedBy[] = 'code';
            }

            if ($label !== null) {
                foreach ($country['names'] ?? [] as $name) {
                    if (is_array($name)
                        && ($name['language_usable'] ?? null) === true
                        && is_string($name['name'] ?? null)
                        && mb_strtolower(trim($name['name'])) === mb_strtolower($label)
                    ) {
                        $matchedBy[] = 'name:'.($name['language_code'] ?? 'unknown');
                    }
                }
            }

            if ($matchedBy !== []) {
                $matches[$country['id']] = array_values(array_unique($matchedBy));
            }
        }

        $candidateIds = array_keys($matches);

        if (count($candidateIds) !== 1) {
            return new CatalogResolution(
                status: $candidateIds === []
                    ? CatalogResolutionStatus::Unresolved
                    : CatalogResolutionStatus::Ambiguous,
                target: null,
                candidateIds: $candidateIds,
                matchedBy: array_values(array_unique(array_merge(...array_values($matches ?: [[]])))),
            );
        }

        return new CatalogResolution(
            status: CatalogResolutionStatus::Proposed,
            target: [
                'owner' => 'NetZeroAdmin',
                'canonical_geography_id' => $candidateIds[0],
                'entity_level' => 'country',
                'catalog_version' => $snapshot->descriptor->version,
                'catalog_sha256' => $snapshot->descriptor->sha256,
            ],
            candidateIds: $candidateIds,
            matchedBy: $matches[$candidateIds[0]],
        );
    }

    private function nonEmpty(?string $value): ?string
    {
        $value = $value === null ? null : trim($value);

        return $value === '' ? null : $value;
    }
}
