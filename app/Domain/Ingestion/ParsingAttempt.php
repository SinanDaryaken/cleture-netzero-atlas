<?php

namespace App\Domain\Ingestion;

final readonly class ParsingAttempt
{
    public function __construct(
        public string $runId,
        public string $releaseId,
        public RawAssetToParse $rawAsset,
        public ?StoredParsedArtifact $existingParsedArtifact = null,
    ) {}
}
