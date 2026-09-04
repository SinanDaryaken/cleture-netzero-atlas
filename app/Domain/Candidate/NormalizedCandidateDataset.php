<?php

namespace App\Domain\Candidate;

use InvalidArgumentException;

final readonly class NormalizedCandidateDataset
{
    /**
     * @param  list<NormalizationFinding>  $findings
     * @param  array<string, int>  $metrics
     */
    public function __construct(
        public string $temporaryPath,
        public string $format,
        public string $normalizerVersion,
        public string $candidateSchemaVersion,
        public string $candidateSchemaSha256,
        public int $candidateCount,
        public int $findingCount,
        public int $fileSize,
        public string $sha256,
        public array $findings,
        public array $metrics,
    ) {
        if (! is_file($this->temporaryPath)) {
            throw new InvalidArgumentException('Normalized candidate dataset temporary file does not exist.');
        }

        if ($this->format !== 'ndjson' || $this->normalizerVersion === '' || $this->candidateSchemaVersion === '') {
            throw new InvalidArgumentException('Normalized candidate dataset contract identity is invalid.');
        }

        if ($this->candidateCount < 1 || $this->findingCount < 0 || $this->fileSize < 1
            || $this->findingCount !== count($this->findings)
        ) {
            throw new InvalidArgumentException('Normalized candidate dataset counts are invalid.');
        }

        foreach ([$this->candidateSchemaSha256, $this->sha256] as $checksum) {
            if (! preg_match('/^[a-f0-9]{64}$/', $checksum)) {
                throw new InvalidArgumentException('Normalized candidate dataset checksums must be lowercase SHA-256 values.');
            }
        }
    }
}
