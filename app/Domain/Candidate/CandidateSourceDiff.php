<?php

namespace App\Domain\Candidate;

use App\Domain\Candidate\Exceptions\CandidateContractViolation;

final readonly class CandidateSourceDiff
{
    /** @param list<array<string, mixed>> $changes */
    public function __construct(
        public string $schemaVersion,
        public string $diffKey,
        public string $logicalKey,
        public string $variantKey,
        public ?string $candidateKey,
        public ?string $previousCandidateKey,
        public string $classification,
        public ?string $beforeComparisonSha256,
        public ?string $afterComparisonSha256,
        public string $comparisonSchemaVersion,
        public string $diffRulesetVersion,
        public array $changes,
    ) {
        if (! in_array($this->classification, ['added', 'changed', 'unchanged', 'removed'], true)) {
            throw new CandidateContractViolation('Candidate source diff classification is invalid.');
        }
    }

    /** @return array<string, mixed> */
    public function toRecord(): array
    {
        return [
            'schema_version' => $this->schemaVersion,
            'diff_key' => $this->diffKey,
            'logical_key' => $this->logicalKey,
            'variant_key' => $this->variantKey,
            'candidate_key' => $this->candidateKey,
            'previous_candidate_key' => $this->previousCandidateKey,
            'classification' => $this->classification,
            'before_comparison_sha256' => $this->beforeComparisonSha256,
            'after_comparison_sha256' => $this->afterComparisonSha256,
            'comparison_schema_version' => $this->comparisonSchemaVersion,
            'diff_ruleset_version' => $this->diffRulesetVersion,
            'changes' => $this->changes,
        ];
    }
}
