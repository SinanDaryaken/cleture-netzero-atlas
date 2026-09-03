<?php

namespace App\Application\Contracts;

use App\Domain\Ingestion\AcquisitionAttempt;
use App\Domain\Ingestion\DownloadedAsset;
use App\Domain\Ingestion\SourceRelease;
use App\Domain\Ingestion\StoredRawAsset;
use Throwable;

interface IngestionLedger
{
    public function beginAcquisition(SourceRelease $release): AcquisitionAttempt;

    public function completeAcquisition(
        AcquisitionAttempt $attempt,
        SourceRelease $release,
        DownloadedAsset $downloadedAsset,
        StoredRawAsset $storedRawAsset,
    ): void;

    public function failAcquisition(AcquisitionAttempt $attempt, Throwable $exception): void;
}
