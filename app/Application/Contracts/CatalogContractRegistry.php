<?php

namespace App\Application\Contracts;

use App\Domain\Catalog\CatalogContract;
use App\Domain\Catalog\CatalogContractDocument;

interface CatalogContractRegistry
{
    public function get(CatalogContract $contract): CatalogContractDocument;
}
