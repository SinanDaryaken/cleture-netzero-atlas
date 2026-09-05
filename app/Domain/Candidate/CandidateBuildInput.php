<?php

namespace App\Domain\Candidate;

final readonly class CandidateBuildInput
{
    public function __construct(
        public string $normalizedArtifactId,
        public string $sourceId,
        public string $sourceReleaseId,
        public array $source,
        public array $release,
        public array $rawAssets,
        public array $pipeline,
        public StoredNormalizedArtifact $artifact,
        public string $licenseTitle,
    ) {}
}
