<?php

namespace App\Application\Contracts;

use App\Domain\Ingestion\SourceRelease;

interface SourceDiscoveryAdapter
{
    public function sourceCode(): string;

    public function discover(): SourceRelease;
}
