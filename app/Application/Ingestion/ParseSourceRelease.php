<?php

namespace App\Application\Ingestion;

use App\Application\Contracts\ParsingLedger;
use App\Application\Contracts\ProcessingArtifactStorage;
use App\Application\Contracts\RawAssetStreamReader;
use App\Domain\Ingestion\ParsedDataset;
use App\Domain\Ingestion\SourceParsingResult;
use Throwable;

final readonly class ParseSourceRelease
{
    public function __construct(
        private SourceParserRegistry $registry,
        private ParsingLedger $ledger,
        private RawAssetStreamReader $rawAssets,
        private ProcessingArtifactStorage $processingArtifacts,
    ) {}

    public function handle(string $sourceCode): SourceParsingResult
    {
        $parser = $this->registry->for($sourceCode);
        $attempt = $this->ledger->beginParsing($parser->sourceCode(), $parser->parserVersion());

        if ($attempt->existingParsedArtifact !== null) {
            return new SourceParsingResult($attempt->rawAsset, $attempt->existingParsedArtifact);
        }

        $stream = null;
        $dataset = null;

        try {
            $stream = $this->rawAssets->read($attempt->rawAsset);
            $dataset = $parser->parse($stream, $attempt->rawAsset);
            $artifact = $this->processingArtifacts->store($attempt->rawAsset, $dataset);
            $this->ledger->completeParsing($attempt, $dataset, $artifact);

            return new SourceParsingResult($attempt->rawAsset, $artifact);
        } catch (Throwable $exception) {
            $this->ledger->failParsing($attempt, $exception);

            throw $exception;
        } finally {
            if (is_resource($stream)) {
                fclose($stream);
            }

            $this->removeTemporaryDataset($dataset);
        }
    }

    private function removeTemporaryDataset(?ParsedDataset $dataset): void
    {
        if ($dataset !== null && is_file($dataset->temporaryPath)) {
            unlink($dataset->temporaryPath);
        }
    }
}
