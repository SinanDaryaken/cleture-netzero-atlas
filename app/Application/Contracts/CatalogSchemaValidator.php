<?php

namespace App\Application\Contracts;

use App\Domain\Catalog\CatalogContract;

interface CatalogSchemaValidator
{
    /** @param array<string, mixed> $record */
    public function assertValid(CatalogContract $contract, array $record): void;
}
