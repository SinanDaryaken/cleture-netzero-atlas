<?php

namespace App\Domain\Candidate;

use InvalidArgumentException;

final readonly class CanonicalCandidateEntity
{
    /** @param array<string, mixed> $record */
    public function __construct(
        public string $candidateKey,
        public string $recordSha256,
        public array $record,
        public string $canonicalJson,
    ) {
        if ($this->candidateKey === '' || ($this->record['candidate_key'] ?? null) !== $this->candidateKey) {
            throw new InvalidArgumentException('Canonical candidate entity identity is invalid.');
        }

        if (! preg_match('/^[a-f0-9]{64}$/', $this->recordSha256)
            || ($this->record['record_sha256'] ?? null) !== $this->recordSha256
        ) {
            throw new InvalidArgumentException('Canonical candidate entity checksum is invalid.');
        }

        if ($this->canonicalJson === '') {
            throw new InvalidArgumentException('Canonical candidate entity JSON cannot be empty.');
        }
    }
}
