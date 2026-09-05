<?php

namespace App\Domain\Catalog;

enum CatalogResolutionStatus: string
{
    case Proposed = 'proposed';
    case Ambiguous = 'ambiguous';
    case Unresolved = 'unresolved';
}
