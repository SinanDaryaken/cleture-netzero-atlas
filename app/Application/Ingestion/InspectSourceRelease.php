<?php

namespace App\Application\Ingestion;

use App\Domain\Ingestion\SourceRelease;

final readonly class InspectSourceRelease
{
    public function __construct(private SourceAdapterRegistry $registry) {}

    public function handle(string $sourceCode): SourceRelease
    {
        return $this->registry->for($sourceCode)->discover();
    }
}
