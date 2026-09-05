<?php

namespace App\Domain\Candidate;

use App\Domain\Candidate\Exceptions\CandidateContractViolation;

final readonly class CandidateFinding
{
    public function __construct(
        public string $code,
        public string $severity,
        public ?string $candidateKey,
        public string $message,
        public ?string $jsonPointer = null,
        public array $evidenceRefs = [],
        public array $context = [],
    ) {
        if ($code === '' || $message === '' || ! in_array($severity, ['warning', 'review', 'blocking'], true)) {
            throw new CandidateContractViolation('Invalid candidate finding.');
        }
    }
}
