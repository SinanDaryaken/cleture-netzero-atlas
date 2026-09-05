<?php

namespace App\Domain\Candidate;

use App\Domain\Candidate\Exceptions\CandidateContractViolation;

final readonly class StoredCandidatePackage
{
    public function __construct(
        public string $disk,
        public string $archiveObjectKey,
        public string $archiveSha256,
        public int $archiveSize,
        public string $manifestObjectKey,
        public string $manifestSha256,
        public int $manifestSize,
        public bool $archiveAlreadyExisted,
        public bool $manifestAlreadyExisted,
    ) {
        if ($this->disk === ''
            || preg_match('/^[a-f0-9]{64}$/', $this->archiveSha256) !== 1
            || preg_match('/^[a-f0-9]{64}$/', $this->manifestSha256) !== 1
            || $this->archiveSize < 1
            || $this->manifestSize < 1
        ) {
            throw new CandidateContractViolation('Stored candidate package identity is invalid.');
        }
    }
}
