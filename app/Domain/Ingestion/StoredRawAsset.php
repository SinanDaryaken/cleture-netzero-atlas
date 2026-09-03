<?php

namespace App\Domain\Ingestion;

use DateTimeImmutable;
use InvalidArgumentException;

final readonly class StoredRawAsset
{
    public function __construct(
        public string $disk,
        public string $objectKey,
        public string $fileName,
        public string $sourceUrl,
        public ?string $mediaType,
        public int $fileSize,
        public string $sha256,
        public DateTimeImmutable $downloadedAt,
        public bool $alreadyExisted = false,
    ) {
        if ($this->disk === '' || $this->objectKey === '') {
            throw new InvalidArgumentException('Stored raw asset location cannot be empty.');
        }
    }
}
