<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\NormalizationAttempt;
use App\Domain\Candidate\NormalizedCandidateDataset;
use App\Domain\Candidate\StoredNormalizedArtifact;
use Throwable;

interface NormalizationLedger
{
    public function beginNormalization(
        string $sourceCode,
        string $normalizerVersion,
        string $candidateSchemaVersion,
        string $candidateSchemaSha256,
    ): NormalizationAttempt;

    public function completeNormalization(
        NormalizationAttempt $attempt,
        NormalizedCandidateDataset $dataset,
        StoredNormalizedArtifact $artifact,
    ): void;

    public function failNormalization(NormalizationAttempt $attempt, Throwable $exception): void;
}
