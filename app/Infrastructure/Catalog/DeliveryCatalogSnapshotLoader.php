<?php

namespace App\Infrastructure\Catalog;

use App\Application\Catalog\TransferAtlasDelivery;
use App\Application\Contracts\CatalogSnapshotLoader;
use App\Domain\Catalog\CatalogSnapshot;
use App\Domain\Catalog\CatalogType;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;

final readonly class DeliveryCatalogSnapshotLoader implements CatalogSnapshotLoader
{
    /** @param array<string, array{version: string, sha256: string}> $pins */
    public function __construct(private TransferAtlasDelivery $delivery, private string $deliverySha256, private array $pins) {}

    public function load(CatalogType $catalog): CatalogSnapshot
    {
        $pin = $this->pins[$catalog->value] ?? null;
        if (! is_array($pin) || ! is_string($pin['version'] ?? null) || ! is_string($pin['sha256'] ?? null)) {
            throw new CatalogContractViolation('Explicit delivery catalog/version/SHA selection is required.');
        }

        return $this->delivery->read($this->deliverySha256)->catalog($catalog, $pin['version'], $pin['sha256']);
    }
}
