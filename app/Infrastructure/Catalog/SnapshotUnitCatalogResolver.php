<?php

namespace App\Infrastructure\Catalog;

use App\Application\Contracts\CatalogSnapshotLoader;
use App\Application\Contracts\UnitCatalogResolver;
use App\Domain\Catalog\CatalogResolution;
use App\Domain\Catalog\CatalogResolutionStatus;
use App\Domain\Catalog\CatalogType;

final readonly class SnapshotUnitCatalogResolver implements UnitCatalogResolver
{
    public function __construct(private CatalogSnapshotLoader $snapshots) {}

    public function resolve(?string $rawValue): CatalogResolution
    {
        $snapshot = $this->snapshots->load(CatalogType::Unit);
        $rawValue = $rawValue === null ? null : trim($rawValue);
        $matches = [];

        if ($rawValue !== null && $rawValue !== '') {
            foreach ($snapshot->payload['definitions'] as $definition) {
                if (! is_string($definition['id'] ?? null)) {
                    continue;
                }

                $matchedBy = [];

                if (($definition['unit_code'] ?? null) === $rawValue) {
                    $matchedBy[] = 'unit_code';
                }

                if (is_string($definition['unit_symbol'] ?? null)
                    && $definition['unit_symbol'] === $rawValue
                ) {
                    $matchedBy[] = 'unit_symbol';
                }

                if ($matchedBy !== []) {
                    $matches[$definition['id']] = $matchedBy;
                }
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
                'catalog' => 'unit',
                'canonical_id' => $candidateIds[0],
                'catalog_version' => $snapshot->descriptor->version,
                'catalog_sha256' => $snapshot->descriptor->sha256,
            ],
            candidateIds: $candidateIds,
            matchedBy: $matches[$candidateIds[0]],
        );
    }
}
