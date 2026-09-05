<?php

namespace App\Domain\Candidate;

use DateTimeImmutable;
use InvalidArgumentException;

final readonly class ParsedArtifactToNormalize
{
    public function __construct(
        public string $sourceCode,
        public string $datasetId,
        public string $releaseVersion,
        public string $releaseRevisionSha256,
        public string $parsedArtifactId,
        public string $parsedDisk,
        public string $parsedObjectKey,
        public int $parsedRowCount,
        public string $parsedSha256,
        public string $parserVersion,
        public string $rawAssetKey,
        public string $rawAssetSha256,
        public DateTimeImmutable $retrievedAt,
        public ?DateTimeImmutable $sourcePublishedAt,
    ) {
        if ($this->sourceCode === '' || $this->datasetId === '' || $this->releaseVersion === ''
            || $this->parsedArtifactId === '' || $this->parsedDisk === '' || $this->parsedObjectKey === ''
            || $this->parserVersion === '' || $this->rawAssetKey === ''
        ) {
            throw new InvalidArgumentException('Normalization input identity cannot be empty.');
        }

        if ($this->parsedRowCount < 1) {
            throw new InvalidArgumentException('Normalization input row count must be positive.');
        }

        foreach ([$this->releaseRevisionSha256, $this->parsedSha256, $this->rawAssetSha256] as $checksum) {
            if (! preg_match('/^[a-f0-9]{64}$/', $checksum)) {
                throw new InvalidArgumentException('Normalization input checksums must be lowercase SHA-256 values.');
            }
        }
    }

    public function context(string $candidateSchemaVersion): NormalizationContext
    {
        return new NormalizationContext(
            sourceCode: $this->sourceCode,
            datasetId: $this->datasetId,
            releaseVersion: $this->releaseVersion,
            rawAssetKey: $this->rawAssetKey,
            rawAssetSha256: $this->rawAssetSha256,
            parserVersion: $this->parserVersion,
            candidateSchemaVersion: $candidateSchemaVersion,
            retrievedAt: $this->retrievedAt,
            sourcePublishedAt: $this->sourcePublishedAt,
        );
    }
}
