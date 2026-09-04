<?php

namespace App\Domain\Candidate;

use InvalidArgumentException;

final readonly class SourceNormalizationResult
{
    /**
     * @param  list<CandidateEntityDraft>  $candidates
     * @param  list<NormalizationFinding>  $findings
     * @param  array<string, int>  $metrics
     */
    public function __construct(
        public array $candidates,
        public array $findings,
        public array $metrics,
    ) {
        foreach ($this->candidates as $candidate) {
            if (! $candidate instanceof CandidateEntityDraft) {
                throw new InvalidArgumentException('Normalization result contains an invalid candidate.');
            }
        }

        foreach ($this->findings as $finding) {
            if (! $finding instanceof NormalizationFinding) {
                throw new InvalidArgumentException('Normalization result contains an invalid finding.');
            }
        }
    }
}
