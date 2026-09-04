<?php

namespace App\Domain\Ingestion;

use InvalidArgumentException;

final readonly class RawAssetToParse
{
    public function __construct(
        public string $sourceCode,
        public string $releaseVersion,
        public string $releaseRevisionSha256,
        public int $reportedRowCount,
        public string $rawAssetId,
        public string $disk,
        public string $objectKey,
        public int $fileSize,
        public string $sha256,
    ) {
        if ($this->sourceCode === '' || $this->releaseVersion === '') {
            throw new InvalidArgumentException('Raw asset source identity cannot be empty.');
        }

        if ($this->rawAssetId === '' || $this->disk === '' || $this->objectKey === '') {
            throw new InvalidArgumentException('Raw asset storage identity cannot be empty.');
        }

        if ($this->reportedRowCount < 1 || $this->fileSize < 1) {
            throw new InvalidArgumentException('Raw asset row count and file size must be positive.');
        }

        if (! preg_match('/^[a-f0-9]{64}$/', $this->releaseRevisionSha256)
            || ! preg_match('/^[a-f0-9]{64}$/', $this->sha256)
        ) {
            throw new InvalidArgumentException('Raw asset checksums must be lowercase SHA-256 values.');
        }
    }
}
