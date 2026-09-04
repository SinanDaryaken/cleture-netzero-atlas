<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\NormalizationContext;
use App\Domain\Candidate\SourceNormalizationResult;
use App\Domain\Ingestion\ParsedObservation;

interface SourceNormalizationAdapter
{
    public function sourceCode(): string;

    public function normalizerVersion(): string;

    /** @param iterable<ParsedObservation> $observations */
    public function normalize(iterable $observations, NormalizationContext $context): SourceNormalizationResult;
}
