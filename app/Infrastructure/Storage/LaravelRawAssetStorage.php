<?php

namespace App\Infrastructure\Storage;

use App\Application\Contracts\RawAssetStorage;
use App\Domain\Ingestion\DownloadedAsset;
use App\Domain\Ingestion\SourceRelease;
use App\Domain\Ingestion\StoredRawAsset;
use Illuminate\Filesystem\FilesystemManager;
use RuntimeException;

final readonly class LaravelRawAssetStorage implements RawAssetStorage
{
    public function __construct(
        private FilesystemManager $filesystems,
        private string $disk,
    ) {}

    public function store(SourceRelease $release, DownloadedAsset $asset): StoredRawAsset
    {
        $filesystem = $this->filesystems->disk($this->disk);
        $objectKey = $this->objectKey($release, $asset);
        $alreadyExisted = $filesystem->exists($objectKey);

        if (! $alreadyExisted) {
            $stream = fopen($asset->temporaryPath, 'rb');

            if ($stream === false) {
                throw new RuntimeException('Raw asset could not be opened for object storage.');
            }

            try {
                if (! $filesystem->put($objectKey, $stream)) {
                    throw new RuntimeException('Raw asset could not be written to object storage.');
                }
            } finally {
                fclose($stream);
            }
        }

        return new StoredRawAsset(
            disk: $this->disk,
            objectKey: $objectKey,
            fileName: $asset->fileName,
            sourceUrl: $asset->sourceUrl,
            mediaType: $asset->mediaType,
            fileSize: $asset->fileSize,
            sha256: $asset->sha256,
            downloadedAt: $asset->downloadedAt,
            alreadyExisted: $alreadyExisted,
        );
    }

    private function objectKey(SourceRelease $release, DownloadedAsset $asset): string
    {
        $datePath = $asset->downloadedAt->format('Y/m/d');
        $sourcePath = mb_strtolower($release->sourceCode);
        $fileName = basename($asset->fileName);

        return "sources/{$sourcePath}/{$datePath}/{$asset->sha256}/{$fileName}";
    }
}
