<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\CandidateContractDocument;

interface CandidateContractRegistry
{
    public function get(CandidateContract $contract): CandidateContractDocument;

    /**
     * @return list<string>
     */
    public function missingPackageRecordContracts(): array;

    public function assertPackageBuildReady(): void;
}
