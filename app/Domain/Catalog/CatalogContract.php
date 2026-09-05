<?php

namespace App\Domain\Catalog;

enum CatalogContract: string
{
    case Geography = 'geography';
    case Unit = 'unit';
    case Descriptor = 'descriptor';
}
