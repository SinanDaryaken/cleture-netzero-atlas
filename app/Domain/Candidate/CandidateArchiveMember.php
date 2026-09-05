<?php

namespace App\Domain\Candidate;

use InvalidArgumentException;

final readonly class CandidateArchiveMember
{
    public function __construct(
        public string $path,
        public string $temporaryPath,
        public string $sha256,
        public int $sizeBytes,
        public int $recordCount,
        public string $mediaType = 'application/x-ndjson',
    ) {
        if (! in_array($this->path, [
            'entities.ndjson',
            'relationships.ndjson',
            'findings.ndjson',
            'source-diff.ndjson',
        ], true)
            || ! is_file($this->temporaryPath)
            || ! preg_match('/^[a-f0-9]{64}$/', $this->sha256)
            || $this->sizeBytes < 0
            || $this->recordCount < 0
            || $this->mediaType !== 'application/x-ndjson'
            || filesize($this->temporaryPath) !== $this->sizeBytes
            || ! hash_equals($this->sha256, hash_file('sha256', $this->temporaryPath))
        ) {
            throw new InvalidArgumentException('Candidate archive member identity is invalid.');
        }

        if (($this->path === 'entities.ndjson' && ($this->sizeBytes < 1 || $this->recordCount < 1))
            || ($this->path === 'relationships.ndjson' && (
                $this->sizeBytes !== 0
                || $this->recordCount !== 0
                || $this->sha256 !== hash('sha256', '')
            ))
        ) {
            throw new InvalidArgumentException('Candidate archive member policy is invalid.');
        }
    }
}
