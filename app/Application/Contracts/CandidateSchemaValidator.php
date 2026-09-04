<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidateContract;

interface CandidateSchemaValidator
{
    /** @param array<string, mixed> $record */
    public function assertValid(CandidateContract $contract, array $record): void;
}
