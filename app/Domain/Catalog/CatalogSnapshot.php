<?php

namespace App\Domain\Catalog;

use InvalidArgumentException;

final readonly class CatalogSnapshot
{
    /** @param array<string, mixed> $payload */
    public function __construct(
        public CatalogSnapshotDescriptor $descriptor,
        public array $payload,
    ) {
        if (($this->payload['schema_version'] ?? null) !== $this->descriptor->contentSchemaVersion) {
            throw new InvalidArgumentException('Catalog payload schema version does not match its descriptor.');
        }
    }
}
