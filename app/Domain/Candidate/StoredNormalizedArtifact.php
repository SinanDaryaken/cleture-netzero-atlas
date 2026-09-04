<?php

namespace App\Domain\Candidate;

final readonly class StoredNormalizedArtifact
{
    public function __construct(
        public string $disk,
        public string $objectKey,
        public string $format,
        public string $normalizerVersion,
        public string $candidateSchemaVersion,
        public string $candidateSchemaSha256,
        public int $candidateCount,
        public int $findingCount,
        public int $fileSize,
        public string $sha256,
        public bool $alreadyExisted,
    ) {}
}
