<?php

namespace App\Domain\Ingestion;

use DateTimeImmutable;
use InvalidArgumentException;

final readonly class SourceRelease
{
    /**
     * @param  array<string, scalar|null>  $metadata
     */
    public function __construct(
        public string $sourceCode,
        public string $datasetId,
        public string $version,
        public string $revisionSha256,
        public int $reportedRowCount,
        public string $assetUrl,
        public string $fileName,
        public int $fileSize,
        public string $upstreamChecksumAlgorithm,
        public string $upstreamChecksum,
        public string $licenseTitle,
        public ?DateTimeImmutable $sourceUpdatedAt,
        public array $metadata = [],
    ) {
        if ($this->sourceCode === '') {
            throw new InvalidArgumentException('Source code cannot be empty.');
        }

        if ($this->datasetId === '' || $this->version === '') {
            throw new InvalidArgumentException('Dataset identity cannot be empty.');
        }

        if (! preg_match('/^[a-f0-9]{64}$/', $this->revisionSha256)) {
            throw new InvalidArgumentException('Release revision must be a lowercase SHA-256 value.');
        }

        if ($this->reportedRowCount < 1 || $this->fileSize < 1) {
            throw new InvalidArgumentException('Release row count and file size must be positive.');
        }

        if (filter_var($this->assetUrl, FILTER_VALIDATE_URL) === false) {
            throw new InvalidArgumentException('Release asset URL is invalid.');
        }
    }
}
