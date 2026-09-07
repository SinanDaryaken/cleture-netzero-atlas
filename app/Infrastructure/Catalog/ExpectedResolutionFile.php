<?php

namespace App\Infrastructure\Catalog;

use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use App\Domain\Catalog\SortedCatalogJson;
use stdClass;

final readonly class ExpectedResolutionFile
{
    public function __construct(private SortedCatalogJson $json) {}

    public function read(string $path): stdClass
    {
        if (! is_file($path)) {
            throw new CatalogContractViolation('Expected resolution must be an explicit local file.');
        }
        $bytes = @file_get_contents($path, false, null, 0, 16385);
        if (! is_string($bytes) || strlen($bytes) > 16384) {
            throw new CatalogContractViolation('Expected resolution file is unavailable or exceeds its byte limit.');
        }

        return $this->json->decode($bytes);
    }
}
