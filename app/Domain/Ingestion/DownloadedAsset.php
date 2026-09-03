<?php

namespace App\Domain\Ingestion;

use DateTimeImmutable;
use InvalidArgumentException;

final readonly class DownloadedAsset
{
    public function __construct(
        public string $temporaryPath,
        public string $fileName,
        public string $sourceUrl,
        public ?string $mediaType,
        public int $fileSize,
        public string $sha256,
        public DateTimeImmutable $downloadedAt,
    ) {
        if (! is_file($this->temporaryPath)) {
            throw new InvalidArgumentException('Downloaded asset does not exist.');
        }

        if ($this->fileSize < 1 || ! preg_match('/^[a-f0-9]{64}$/', $this->sha256)) {
            throw new InvalidArgumentException('Downloaded asset identity is invalid.');
        }
    }
}
