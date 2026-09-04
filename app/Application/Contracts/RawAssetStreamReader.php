<?php

namespace App\Application\Contracts;

use App\Domain\Ingestion\RawAssetToParse;

interface RawAssetStreamReader
{
    /**
     * @return resource
     */
    public function read(RawAssetToParse $rawAsset): mixed;
}
