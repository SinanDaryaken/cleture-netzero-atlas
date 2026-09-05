<?php

namespace App\Domain\Candidate;

use DateTimeImmutable;
use InvalidArgumentException;

final readonly class NormalizationContext
{
    public function __construct(
        public string $sourceCode,
        public string $datasetId,
        public string $releaseVersion,
        public string $rawAssetKey,
        public string $rawAssetSha256,
        public string $parserVersion,
        public string $candidateSchemaVersion,
        public DateTimeImmutable $retrievedAt,
        public ?DateTimeImmutable $sourcePublishedAt = null,
    ) {
        if ($this->sourceCode === '' || $this->datasetId === '' || $this->releaseVersion === ''
            || $this->rawAssetKey === '' || $this->parserVersion === ''
            || preg_match('/^\d+\.\d+\.\d+$/', $this->candidateSchemaVersion) !== 1
        ) {
            throw new InvalidArgumentException('Normalization context identity cannot be empty.');
        }

        if (! preg_match('/^[a-f0-9]{64}$/', $this->rawAssetSha256)) {
            throw new InvalidArgumentException('Normalization raw asset checksum must be a lowercase SHA-256 value.');
        }

        if (strlen($this->rawAssetKey) > 1024
            || preg_match('#^(?!/)(?!.*(?:^|/)\.\.(?:/|$))(?![A-Za-z][A-Za-z0-9+.-]*://)[A-Za-z0-9._/-]+$#', $this->rawAssetKey) !== 1
        ) {
            throw new InvalidArgumentException('Normalization raw asset key must be a safe relative object key.');
        }
    }
}
