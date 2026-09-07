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
        $schemas = match ($this->catalog) {
            CatalogType::Unit => ['atlas-catalog-snapshot/v1' => 'unit-catalog-release/v1', 'atlas-catalog-snapshot/v2' => 'unit-catalog-release/v2'],
            CatalogType::Geography => ['atlas-catalog-snapshot/v1' => 'netzero-geography-snapshot/v1'],
            CatalogType::Currency => ['netzero-currency-snapshot-descriptor/v1' => 'netzero-currency-snapshot/v1'],
            CatalogType::Taxonomy => ['netzero-review-catalog-descriptor/v1' => 'netzero-taxonomy-snapshot/v1'],
            CatalogType::IntendedUse => ['netzero-review-catalog-descriptor/v1' => 'netzero-intended-use-snapshot/v1'],
        };
        if (! isset($schemas[$this->schemaVersion])
            || $this->owner !== 'NetZeroAdmin'
            || $this->version === ''
            || $this->canonicalization !== 'netzero-sorted-json-v1'
            || ! preg_match('/^[a-f0-9]{64}$/', $this->sha256)
            || $this->sizeBytes < 1
            || $this->artifactPath !== "atlas-catalog-snapshots/{$this->catalog->value}/sha256/{$this->sha256}.json"
        ) {
            throw new InvalidArgumentException('Catalog snapshot descriptor identity is invalid.');
        }

        $expectedContentSchema = $schemas[$this->schemaVersion];

        if ($this->contentSchemaVersion !== $expectedContentSchema
            || ! str_contains($this->artifactPath, "/{$this->catalog->value}/")
            || ! str_ends_with($this->artifactPath, "/{$this->sha256}.json")
            || ($this->catalog !== CatalogType::Unit && $this->version !== "sha256:{$this->sha256}")
        ) {
            throw new InvalidArgumentException('Catalog snapshot descriptor does not match its catalog payload.');
        }
    }
}
