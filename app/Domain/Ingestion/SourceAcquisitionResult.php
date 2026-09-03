<?php

namespace App\Domain\Ingestion;

final readonly class SourceAcquisitionResult
{
    public function __construct(
        public SourceRelease $release,
        public StoredRawAsset $rawAsset,
    ) {}
}
