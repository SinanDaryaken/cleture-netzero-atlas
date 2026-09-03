<?php

namespace App\Application\Contracts;

use App\Domain\Ingestion\DownloadedAsset;
use App\Domain\Ingestion\SourceRelease;

interface SourceAcquisitionAdapter extends SourceDiscoveryAdapter
{
    public function download(SourceRelease $release): DownloadedAsset;
}
