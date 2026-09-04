<?php

namespace App\Application\Contracts;

use App\Domain\Ingestion\ParsedDataset;
use App\Domain\Ingestion\RawAssetToParse;

interface SourceParsingAdapter
{
    public function sourceCode(): string;

    public function parserVersion(): string;

    /**
     * @param  resource  $stream
     */
    public function parse(mixed $stream, RawAssetToParse $rawAsset): ParsedDataset;
}
