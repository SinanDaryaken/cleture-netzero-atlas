<?php

namespace App\Domain\Catalog;

use InvalidArgumentException;

final readonly class CatalogResolution
{
    /**
     * @param  array<string, mixed>|null  $target
     * @param  list<string>  $candidateIds
     * @param  list<string>  $matchedBy
     */
    public function __construct(
        public CatalogResolutionStatus $status,
        public ?array $target,
        public array $candidateIds,
        public array $matchedBy,
    ) {
        $valid = match ($this->status) {
            CatalogResolutionStatus::Proposed => $this->target !== null && count($this->candidateIds) === 1,
            CatalogResolutionStatus::Ambiguous => $this->target === null && count($this->candidateIds) > 1,
            CatalogResolutionStatus::Unresolved => $this->target === null && $this->candidateIds === [],
        };

        if (! $valid || count($this->candidateIds) !== count(array_unique($this->candidateIds))) {
            throw new InvalidArgumentException('Catalog resolution state is inconsistent.');
        }
    }
}
