<?php

namespace App\Infrastructure\Storage;

use App\Application\Contracts\RawAssetStreamReader;
use App\Domain\Ingestion\RawAssetToParse;
use Illuminate\Filesystem\FilesystemManager;
use RuntimeException;

final readonly class LaravelRawAssetStreamReader implements RawAssetStreamReader
{
    public function __construct(private FilesystemManager $filesystems) {}

    /**
     * @return resource
     */
    public function read(RawAssetToParse $rawAsset): mixed
    {
        $stream = $this->filesystems
            ->disk($rawAsset->disk)
            ->readStream($rawAsset->objectKey);

        if (! is_resource($stream)) {
            throw new RuntimeException('Raw asset could not be opened for parsing.');
        }

        return $stream;
    }
}
