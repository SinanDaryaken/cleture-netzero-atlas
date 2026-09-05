<?php

namespace App\Application\Contracts;

use App\Domain\Catalog\CatalogResolution;

interface UnitCatalogResolver
{
    public function resolve(?string $rawValue): CatalogResolution;
}
