<?php

namespace App\Application\Ingestion;

use App\Application\Contracts\IngestionLedger;
use App\Application\Contracts\RawAssetStorage;
use App\Application\Contracts\SourceAcquisitionAdapter;
use App\Domain\Ingestion\DownloadedAsset;
use App\Domain\Ingestion\SourceAcquisitionResult;
use LogicException;
use Throwable;

final readonly class AcquireSourceRelease
{
    public function __construct(
        private SourceAdapterRegistry $registry,
        private IngestionLedger $ledger,
        private RawAssetStorage $storage,
    ) {}

    public function handle(string $sourceCode): SourceAcquisitionResult
    {
        $adapter = $this->registry->for($sourceCode);

        if (! $adapter instanceof SourceAcquisitionAdapter) {
            throw new LogicException("Source adapter does not support acquisition: {$sourceCode}");
        }

        $release = $adapter->discover();
        $attempt = $this->ledger->beginAcquisition($release);

        if ($attempt->existingRawAsset !== null) {
            return new SourceAcquisitionResult($release, $attempt->existingRawAsset);
        }

        $downloadedAsset = null;

        try {
            $downloadedAsset = $adapter->download($release);
            $storedRawAsset = $this->storage->store($release, $downloadedAsset);
            $this->ledger->completeAcquisition(
                $attempt,
                $release,
                $downloadedAsset,
                $storedRawAsset,
            );

            return new SourceAcquisitionResult($release, $storedRawAsset);
        } catch (Throwable $exception) {
            $this->ledger->failAcquisition($attempt, $exception);

            throw $exception;
        } finally {
            $this->removeTemporaryAsset($downloadedAsset);
        }
    }

    private function removeTemporaryAsset(?DownloadedAsset $asset): void
    {
        if ($asset !== null && is_file($asset->temporaryPath)) {
            unlink($asset->temporaryPath);
        }
    }
}
