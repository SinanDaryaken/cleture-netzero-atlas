<?php

namespace App\Application\Contracts;

use App\Domain\Ingestion\ParsedDataset;
use App\Domain\Ingestion\ParsingAttempt;
use App\Domain\Ingestion\StoredParsedArtifact;
use Throwable;

interface ParsingLedger
{
    public function beginParsing(string $sourceCode, string $parserVersion): ParsingAttempt;

    public function completeParsing(
        ParsingAttempt $attempt,
        ParsedDataset $dataset,
        StoredParsedArtifact $artifact,
    ): void;

    public function failParsing(ParsingAttempt $attempt, Throwable $exception): void;
}
