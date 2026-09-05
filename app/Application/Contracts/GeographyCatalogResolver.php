<?php

namespace App\Application\Contracts;

use App\Domain\Catalog\CatalogResolution;

interface GeographyCatalogResolver
{
    public function resolveCountry(?string $rawCode, ?string $rawLabel): CatalogResolution;
}
