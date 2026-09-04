<?php

namespace App\Domain\Ingestion;

use InvalidArgumentException;

final readonly class StoredParsedArtifact
{
    public function __construct(
        public string $disk,
        public string $objectKey,
        public string $format,
        public string $parserVersion,
        public string $schemaVersion,
        public string $schemaSha256,
        public string $sourceEncoding,
        public int $rowCount,
        public int $fileSize,
        public string $sha256,
        public bool $alreadyExisted = false,
    ) {
        if ($this->disk === '' || $this->objectKey === '') {
            throw new InvalidArgumentException('Parsed artifact location cannot be empty.');
        }
    }
}
