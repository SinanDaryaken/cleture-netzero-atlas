<?php

namespace App\Domain\Ingestion;

use InvalidArgumentException;

final readonly class ParsedDataset
{
    /**
     * @param  array<string, int>  $metrics
     */
    public function __construct(
        public string $temporaryPath,
        public string $format,
        public string $parserVersion,
        public string $schemaVersion,
        public string $schemaSha256,
        public string $sourceEncoding,
        public int $rowCount,
        public int $fileSize,
        public string $sha256,
        public array $metrics,
    ) {
        if (! is_file($this->temporaryPath)) {
            throw new InvalidArgumentException('Parsed dataset temporary file does not exist.');
        }

        if ($this->format === '' || $this->parserVersion === '' || $this->schemaVersion === '') {
            throw new InvalidArgumentException('Parsed dataset contract identity cannot be empty.');
        }

        if ($this->rowCount < 1 || $this->fileSize < 1) {
            throw new InvalidArgumentException('Parsed dataset row count and file size must be positive.');
        }

        if (! preg_match('/^[a-f0-9]{64}$/', $this->schemaSha256)
            || ! preg_match('/^[a-f0-9]{64}$/', $this->sha256)
        ) {
            throw new InvalidArgumentException('Parsed dataset checksums must be lowercase SHA-256 values.');
        }
    }
}
