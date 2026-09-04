<?php

namespace App\Domain\Candidate;

use InvalidArgumentException;

final readonly class SourceNormalizationResult
{
    /**
     * @param  iterable<CandidateEntityDraft>  $candidates
     * @param  list<NormalizationFinding>  $findings
     * @param  array<string, int>  $metrics
     */
    public function __construct(
        public iterable $candidates,
        public array $findings,
        public array $metrics,
    ) {
        foreach ($this->findings as $finding) {
            if (! $finding instanceof NormalizationFinding) {
                throw new InvalidArgumentException('Normalization result contains an invalid finding.');
            }
        }
    }
}
