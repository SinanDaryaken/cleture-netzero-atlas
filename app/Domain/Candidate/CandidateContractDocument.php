<?php

namespace App\Domain\Candidate;

use InvalidArgumentException;

final readonly class CandidateContractDocument
{
    public function __construct(
        public CandidateContract $contract,
        public string $version,
        public string $schemaId,
        public string $sha256,
        public string $contents,
        public string $owner,
        public string $upstreamRepository,
        public string $upstreamCommit,
        public string $upstreamGitBlob,
        public string $upstreamPath,
    ) {
        if (! preg_match('/^\d+\.\d+\.\d+$/', $this->version)) {
            throw new InvalidArgumentException('Candidate contract version must use semantic versioning.');
        }

        if ($this->schemaId === '' || $this->owner === '' || $this->upstreamRepository === '' || $this->upstreamPath === '') {
            throw new InvalidArgumentException('Candidate contract provenance cannot be empty.');
        }

        if (! preg_match('/^[a-f0-9]{64}$/', $this->sha256)) {
            throw new InvalidArgumentException('Candidate contract checksum must be a lowercase SHA-256 value.');
        }

        if (! preg_match('/^[a-f0-9]{40,64}$/', $this->upstreamCommit)
            || ! preg_match('/^[a-f0-9]{40,64}$/', $this->upstreamGitBlob)
        ) {
            throw new InvalidArgumentException('Candidate contract upstream Git identity is invalid.');
        }

        if (! hash_equals($this->sha256, hash('sha256', $this->contents))) {
            throw new InvalidArgumentException('Candidate contract contents do not match the pinned checksum.');
        }
    }
}
