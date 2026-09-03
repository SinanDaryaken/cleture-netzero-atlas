<?php

namespace App\Domain\Ingestion;

final readonly class AcquisitionAttempt
{
    public function __construct(
        public string $runId,
        public string $releaseId,
        public ?StoredRawAsset $existingRawAsset = null,
    ) {}
}
