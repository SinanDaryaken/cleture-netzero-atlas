<?php

namespace App\Domain\Ingestion;

final readonly class SourceParsingResult
{
    public function __construct(
        public RawAssetToParse $rawAsset,
        public StoredParsedArtifact $parsedArtifact,
    ) {}
}
