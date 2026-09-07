<?php

namespace App\Domain\Catalog;

use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use stdClass;

final readonly class VerifiedAtlasDelivery
{
    /** @param array<string, string> $artifacts @param array<string, CatalogSnapshot> $catalogs */
    public function __construct(
        public string $sha256,
        public string $manifestBytes,
        public stdClass $manifest,
        public array $artifacts,
        public array $catalogs,
    ) {}

    public function catalog(CatalogType $type, string $version, string $sha256): CatalogSnapshot
    {
        $catalog = $this->catalogs[$type->value.':'.$sha256] ?? null;
        if ($catalog === null || $catalog->descriptor->version !== $version) {
            throw new CatalogContractViolation('The exact catalog/version/SHA is absent from this delivery.');
        }

        return $catalog;
    }

    /** @return array<string, mixed> */
    public function receipt(): array
    {
        return ['status' => 'catalogs_verified', 'delivery_sha256' => $this->sha256,
            'artifact_count' => count($this->artifacts), 'artifact_bytes' => array_sum(array_map(strlen(...), $this->artifacts)),
            'catalogs' => $this->manifest->catalogs, 'current_approval_verified' => false,
            'resolution_status' => $this->manifest->resolution === null ? 'absent' : 'forensic_only',
            'automatic_mapping_allowed' => false, 'usage_allowed' => false, 'publish_allowed' => false];
    }
}
