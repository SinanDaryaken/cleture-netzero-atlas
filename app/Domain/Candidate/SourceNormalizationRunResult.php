<?php

namespace App\Domain\Candidate;

final readonly class SourceNormalizationRunResult
{
    public function __construct(
        public ParsedArtifactToNormalize $input,
        public StoredNormalizedArtifact $normalizedArtifact,
    ) {}
}
