<?php

namespace App\Domain\Candidate;

use App\Domain\Candidate\Exceptions\CandidateContractViolation;

final readonly class CandidateValidationReceipt
{
    public function __construct(
        public string $identity,
        public string $entitySha256,
        public string $findingSha256,
        public string $rulesetVersion,
        public string $rulesetSha256,
        public array $catalogSnapshots,
        public array $license,
        public array $rawAssets,
        public int $entityCount,
        public array $summary,
        public bool $packageBlocked,
    ) {}

    public function assertPackage(CandidatePackageContext $context, array $members): void
    {
        if ($this->packageBlocked || $members['entities.ndjson']->sha256 !== $this->entitySha256
            || $members['findings.ndjson']->sha256 !== $this->findingSha256
            || $members['entities.ndjson']->recordCount !== $this->entityCount
            || $context->catalogSnapshots !== $this->catalogSnapshots || $context->license !== $this->license
            || $context->rawAssets !== $this->rawAssets
            || ($context->pipeline['validation_ruleset_version'] ?? null) !== $this->rulesetVersion
            || ($context->pipeline['validation_ruleset_sha256'] ?? null) !== $this->rulesetSha256) {
            throw new CandidateContractViolation('Package requires matching, unblocked validation evidence.');
        }
    }
}
