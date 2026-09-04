<?php

namespace App\Domain\Candidate;

final readonly class NormalizationAttempt
{
    public function __construct(
        public string $runId,
        public string $releaseId,
        public ParsedArtifactToNormalize $input,
        public ?StoredNormalizedArtifact $existingArtifact = null,
    ) {}
}
