<?php

namespace App\Application\Contracts;

use App\Domain\Catalog\CatalogSnapshot;
use App\Domain\Catalog\CatalogType;

interface CatalogSnapshotLoader
{
    public function load(CatalogType $catalog): CatalogSnapshot;
}
