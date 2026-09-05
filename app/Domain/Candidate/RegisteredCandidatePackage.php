<?php

namespace App\Domain\Candidate;

final readonly class RegisteredCandidatePackage
{
    public function __construct(
        public string $packageId,
        public string $idempotencyKey,
        public StoredCandidatePackage $storage,
        public bool $alreadyExisted,
    ) {}
}
