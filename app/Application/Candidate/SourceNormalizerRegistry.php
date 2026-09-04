<?php

namespace App\Application\Candidate;

use App\Application\Contracts\SourceNormalizationAdapter;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;

final readonly class SourceNormalizerRegistry
{
    /** @var array<string, SourceNormalizationAdapter> */
    private array $normalizers;

    /** @param iterable<SourceNormalizationAdapter> $normalizers */
    public function __construct(iterable $normalizers)
    {
        $indexed = [];

        foreach ($normalizers as $normalizer) {
            $sourceCode = mb_strtoupper($normalizer->sourceCode());

            if (isset($indexed[$sourceCode])) {
                throw new SourceContractViolation("Duplicate source normalizer registered for {$sourceCode}.");
            }

            $indexed[$sourceCode] = $normalizer;
        }

        $this->normalizers = $indexed;
    }

    public function for(string $sourceCode): SourceNormalizationAdapter
    {
        $normalized = mb_strtoupper(trim($sourceCode));

        return $this->normalizers[$normalized]
            ?? throw new SourceContractViolation("Unknown source normalizer: {$sourceCode}.");
    }
}
