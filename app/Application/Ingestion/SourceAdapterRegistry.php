<?php

namespace App\Application\Ingestion;

use App\Application\Contracts\SourceDiscoveryAdapter;
use InvalidArgumentException;

final readonly class SourceAdapterRegistry
{
    /** @var array<string, SourceDiscoveryAdapter> */
    private array $adapters;

    /**
     * @param  iterable<SourceDiscoveryAdapter>  $adapters
     */
    public function __construct(iterable $adapters)
    {
        $indexed = [];

        foreach ($adapters as $adapter) {
            $sourceCode = mb_strtoupper($adapter->sourceCode());

            if (isset($indexed[$sourceCode])) {
                throw new InvalidArgumentException("Duplicate source adapter: {$sourceCode}");
            }

            $indexed[$sourceCode] = $adapter;
        }

        $this->adapters = $indexed;
    }

    public function for(string $sourceCode): SourceDiscoveryAdapter
    {
        $normalizedCode = mb_strtoupper(trim($sourceCode));

        return $this->adapters[$normalizedCode]
            ?? throw new InvalidArgumentException("Unknown source adapter: {$sourceCode}");
    }
}
