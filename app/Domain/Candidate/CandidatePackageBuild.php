<?php

namespace App\Domain\Candidate;

final readonly class CandidatePackageBuild
{
    /** @param array<string, mixed> $manifest */
    public function __construct(
        public CandidatePackageArtifact $artifact,
        public array $manifest,
        public string $canonicalManifestJson,
    ) {}
}
