<?php

namespace App\Application\Candidate;

use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Candidate\CanonicalCandidateEntity;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;

final readonly class BuildV2CandidateEntity
{
    public function __construct(
        private ResolveCandidateCatalogMappings $catalogMappings,
        private BuildCanonicalCandidateEntity $canonicalEntity,
    ) {}

    public function handle(CandidateEntityDraft $draft): CanonicalCandidateEntity
    {
        if ($draft->schemaVersion !== '2.0.0') {
            throw new CandidateContractViolation('Candidate V2 builder requires a 2.0.0 draft.');
        }

        return $this->canonicalEntity->handle($this->catalogMappings->handle($draft));
    }
}
