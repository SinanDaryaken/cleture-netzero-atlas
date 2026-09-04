<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\NormalizedCandidateDataset;
use App\Domain\Candidate\ParsedArtifactToNormalize;
use App\Domain\Candidate\StoredNormalizedArtifact;

interface NormalizedArtifactStorage
{
    public function store(
        ParsedArtifactToNormalize $input,
        NormalizedCandidateDataset $dataset,
    ): StoredNormalizedArtifact;
}
