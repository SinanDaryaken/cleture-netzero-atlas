<?php

namespace App\Domain\Catalog;

use InvalidArgumentException;

final readonly class CatalogSnapshotDescriptor
{
    public function __construct(
        public CatalogType $catalog,
        public string $schemaVersion,
        public string $owner,
        public string $version,
        public string $contentSchemaVersion,
        public string $canonicalization,
        public string $sha256,
        public int $sizeBytes,
        public string $artifactPath,
    ) {
        if ($this->schemaVersion !== 'atlas-catalog-snapshot/v1'
            || $this->owner !== 'NetZeroAdmin'
            || $this->version === ''
            || $this->canonicalization !== 'netzero-sorted-json-v1'
            || ! preg_match('/^[a-f0-9]{64}$/', $this->sha256)
            || $this->sizeBytes < 1
            || preg_match('#^atlas-catalog-snapshots/(unit|geography)/sha256/[a-f0-9]{64}\.json$#', $this->artifactPath) !== 1
        ) {
            throw new InvalidArgumentException('Catalog snapshot descriptor identity is invalid.');
        }

        $expectedContentSchema = match ($this->catalog) {
            CatalogType::Geography => 'netzero-geography-snapshot/v1',
            CatalogType::Unit => 'unit-catalog-release/v1',
        };

        if ($this->contentSchemaVersion !== $expectedContentSchema
            || ! str_contains($this->artifactPath, "/{$this->catalog->value}/")
            || ! str_ends_with($this->artifactPath, "/{$this->sha256}.json")
            || ($this->catalog === CatalogType::Geography && $this->version !== "sha256:{$this->sha256}")
        ) {
            throw new InvalidArgumentException('Catalog snapshot descriptor does not match its catalog payload.');
        }
    }
}
