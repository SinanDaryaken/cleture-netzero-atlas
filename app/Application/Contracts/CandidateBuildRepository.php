<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidateBuildInput;
use App\Domain\Candidate\ValidatedCandidateDataset;

interface CandidateBuildRepository
{
    public function input(string $normalizedArtifactId): CandidateBuildInput;

    public function normalizationFindings(string $normalizedArtifactId): iterable;

    public function recordValidation(string $normalizedArtifactId, ValidatedCandidateDataset $dataset): void;

    public function begin(CandidateBuildInput $input, string $identity): string;

    public function finish(string $runId, string $status, array $metrics): void;
}
