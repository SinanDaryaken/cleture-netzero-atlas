<?php

namespace App\Application\Ingestion;

use App\Application\Contracts\SourceParsingAdapter;
use InvalidArgumentException;

final readonly class SourceParserRegistry
{
    /** @var array<string, SourceParsingAdapter> */
    private array $parsers;

    /**
     * @param  iterable<SourceParsingAdapter>  $parsers
     */
    public function __construct(iterable $parsers)
    {
        $indexed = [];

        foreach ($parsers as $parser) {
            $sourceCode = mb_strtoupper($parser->sourceCode());

            if (isset($indexed[$sourceCode])) {
                throw new InvalidArgumentException("Duplicate source parser: {$sourceCode}");
            }

            $indexed[$sourceCode] = $parser;
        }

        $this->parsers = $indexed;
    }

    public function for(string $sourceCode): SourceParsingAdapter
    {
        $normalizedCode = mb_strtoupper(trim($sourceCode));

        return $this->parsers[$normalizedCode]
            ?? throw new InvalidArgumentException("Unknown source parser: {$sourceCode}");
    }
}
