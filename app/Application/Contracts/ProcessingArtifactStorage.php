<?php

namespace App\Application\Contracts;

use App\Domain\Ingestion\ParsedDataset;
use App\Domain\Ingestion\RawAssetToParse;
use App\Domain\Ingestion\StoredParsedArtifact;

interface ProcessingArtifactStorage
{
    public function store(RawAssetToParse $rawAsset, ParsedDataset $dataset): StoredParsedArtifact;
}
