<?php

namespace App\Application\Contracts;

use App\Domain\Ingestion\DownloadedAsset;
use App\Domain\Ingestion\SourceRelease;
use App\Domain\Ingestion\StoredRawAsset;

interface RawAssetStorage
{
    public function store(SourceRelease $release, DownloadedAsset $asset): StoredRawAsset;
}
