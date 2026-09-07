<?php

namespace App\Domain\Catalog;

enum CatalogType: string
{
    case Geography = 'geography';
    case Unit = 'unit';
    case Currency = 'currency';
    case Taxonomy = 'taxonomy';
    case IntendedUse = 'intended_use';

    public function contract(): CatalogContract
    {
        return match ($this) {
            self::Geography => CatalogContract::Geography,
            self::Unit => CatalogContract::Unit,
            default => throw new Exceptions\CatalogContractViolation('This catalog requires the delivery contract registry.'),
        };
    }
}
