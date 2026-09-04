<?php

namespace App\Infrastructure\Storage;

use App\Application\Contracts\ProcessingArtifactStorage;
use App\Domain\Ingestion\ParsedDataset;
use App\Domain\Ingestion\RawAssetToParse;
use App\Domain\Ingestion\StoredParsedArtifact;
use Illuminate\Filesystem\FilesystemManager;
use RuntimeException;

final readonly class LaravelProcessingArtifactStorage implements ProcessingArtifactStorage
{
    public function __construct(
        private FilesystemManager $filesystems,
        private string $disk,
    ) {}

    public function store(RawAssetToParse $rawAsset, ParsedDataset $dataset): StoredParsedArtifact
    {
        $filesystem = $this->filesystems->disk($this->disk);
        $objectKey = $this->objectKey($rawAsset, $dataset);
        $alreadyExisted = $filesystem->exists($objectKey);

        if (! $alreadyExisted) {
            $stream = fopen($dataset->temporaryPath, 'rb');

            if ($stream === false) {
                throw new RuntimeException('Parsed artifact could not be opened for object storage.');
            }

            try {
                if (! $filesystem->put($objectKey, $stream)) {
                    throw new RuntimeException('Parsed artifact could not be written to object storage.');
                }
            } finally {
                fclose($stream);
            }
        }

        if ($filesystem->size($objectKey) !== $dataset->fileSize) {
            throw new RuntimeException('Stored parsed artifact size verification failed.');
        }

        return new StoredParsedArtifact(
            disk: $this->disk,
            objectKey: $objectKey,
            format: $dataset->format,
            parserVersion: $dataset->parserVersion,
            schemaVersion: $dataset->schemaVersion,
            schemaSha256: $dataset->schemaSha256,
            sourceEncoding: $dataset->sourceEncoding,
            rowCount: $dataset->rowCount,
            fileSize: $dataset->fileSize,
            sha256: $dataset->sha256,
            alreadyExisted: $alreadyExisted,
        );
    }

    private function objectKey(RawAssetToParse $rawAsset, ParsedDataset $dataset): string
    {
        $sourcePath = mb_strtolower($rawAsset->sourceCode);
        $extension = $dataset->format === 'ndjson' ? 'ndjson' : $dataset->format;

        return "sources/{$sourcePath}/releases/{$rawAsset->releaseRevisionSha256}"
            ."/parsed/{$dataset->parserVersion}/{$dataset->sha256}.{$extension}";
    }
}
