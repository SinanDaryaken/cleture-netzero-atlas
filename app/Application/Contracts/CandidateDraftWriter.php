<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidateContractDocument;
use App\Domain\Candidate\NormalizedCandidateDataset;
use App\Domain\Candidate\SourceNormalizationResult;

interface CandidateDraftWriter
{
    public function write(
        SourceNormalizationResult $result,
        string $normalizerVersion,
        CandidateContractDocument $entityContract,
    ): NormalizedCandidateDataset;
}
