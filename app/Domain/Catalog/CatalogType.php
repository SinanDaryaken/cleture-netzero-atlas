<?php

namespace App\Domain\Catalog;

enum CatalogType: string
{
    case Geography = 'geography';
    case Unit = 'unit';

    public function contract(): CatalogContract
    {
        return match ($this) {
            self::Geography => CatalogContract::Geography,
            self::Unit => CatalogContract::Unit,
        };
    }
}
