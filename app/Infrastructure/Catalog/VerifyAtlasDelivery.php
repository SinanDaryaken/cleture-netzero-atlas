<?php

namespace App\Infrastructure\Catalog;

use App\Application\Contracts\AtlasDeliveryVerifier;
use App\Domain\Catalog\CatalogSnapshot;
use App\Domain\Catalog\CatalogSnapshotDescriptor;
use App\Domain\Catalog\CatalogType;
use App\Domain\Catalog\DeliveryCatalogIntegrity;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use App\Domain\Catalog\SortedCatalogJson;
use App\Domain\Catalog\VerifiedAtlasDelivery;
use App\Infrastructure\Contracts\PinnedDeliveryContracts;

final readonly class VerifyAtlasDelivery implements AtlasDeliveryVerifier
{
    public function __construct(private PinnedDeliveryContracts $contracts, private SortedCatalogJson $json,
        private DeliveryCatalogIntegrity $integrity, private VerifyDeliveredResolution $resolutions) {}

    /** @param callable(string, int): string $read */
    public function verify(string $expectedSha256, callable $read): VerifiedAtlasDelivery
    {
        if (! preg_match('/\A[a-f0-9]{64}\z/', $expectedSha256)) {
            throw new CatalogContractViolation('An independent exact manifest SHA-256 is required.');
        }
        $bytes = $read('manifest.json', 1048576);
        if (strlen($bytes) > 1048576 || ! hash_equals($expectedSha256, hash('sha256', $bytes))) {
            throw new CatalogContractViolation('Delivery manifest SHA-256 mismatch.');
        }
        $manifest = $this->json->decode($bytes);
        $this->contracts->validate('atlas-delivery-v1.schema.json', $manifest);
        $artifacts = [];
        $total = 0;
        foreach ($manifest->artifacts as $artifact) {
            if (isset($artifacts[$artifact->name]) || array_intersect(explode('/', $artifact->name), ['', '.', '..']) !== []
                || $artifact->object_path !== 'objects/sha256/'.$artifact->sha256) {
                throw new CatalogContractViolation('Duplicate, unsafe or disconnected artifact path.');
            }
            $total += $artifact->size_bytes;
            if ($total > 134217728) {
                throw new CatalogContractViolation('Delivery aggregate size exceeds its bound.');
            }
            $content = $read($artifact->object_path, $artifact->size_bytes);
            if (strlen($content) !== $artifact->size_bytes || ! hash_equals($artifact->sha256, hash('sha256', $content))) {
                throw new CatalogContractViolation('Delivery artifact identity mismatch: '.$artifact->name);
            }
            $artifacts[$artifact->name] = $content;
        }
        $roots = ['atlas-delivery-contract-v1.manifest.json'];
        $catalogs = [];
        foreach ($manifest->catalogs as $pin) {
            $type = CatalogType::from($pin->catalog);
            $path = 'atlas-catalog-snapshots/'.$pin->catalog.'/sha256/'.$pin->sha256.'.json';
            $key = $pin->catalog.':'.$pin->sha256;
            if (isset($catalogs[$key]) || $pin->artifact_name !== $path || $pin->descriptor_name !== $path.'.manifest.json'
                || ! isset($artifacts[$path], $artifacts[$pin->descriptor_name])) {
                throw new CatalogContractViolation('Catalog pin is disconnected from delivery artifacts.');
            }
            $descriptor = $this->json->decode($artifacts[$pin->descriptor_name]);
            $payload = $this->json->decode($artifacts[$path]);
            [$root, $descriptorSchema, $payloadSchema] = match ($type) {
                CatalogType::Unit => ['atlas-catalog-contract-v2.1.manifest.json', 'atlas-catalog-descriptor-v2.schema.json', 'atlas-catalog-unit-v2.1.schema.json'],
                CatalogType::Geography => ['atlas-catalog-contract-v2.1.manifest.json', 'atlas-catalog-descriptor-v2.schema.json', 'atlas-catalog-geography-v1.schema.json'],
                CatalogType::Currency => ['factor-context-contract-v1.manifest.json', 'currency-snapshot-descriptor-v1.schema.json', 'currency-snapshot-v1.schema.json'],
                CatalogType::Taxonomy => ['review-catalog-contract-v1.manifest.json', 'review-catalog-descriptor-v1.schema.json', 'review-catalog-taxonomy-v1.schema.json'],
                CatalogType::IntendedUse => ['review-catalog-contract-v1.manifest.json', 'review-catalog-descriptor-v1.schema.json', 'review-catalog-intended-use-v1.schema.json'],
            };
            $roots[] = $root;
            $this->contracts->validate($descriptorSchema, $descriptor);
            $this->contracts->validate($payloadSchema, $payload);
            if ($descriptor->catalog !== $pin->catalog || $descriptor->version !== $pin->version
                || $descriptor->sha256 !== $pin->sha256 || $descriptor->artifact_path !== $path
                || $descriptor->content_schema_version !== $payload->schema_version
                || $descriptor->size_bytes !== strlen($artifacts[$path]) || hash('sha256', $artifacts[$path]) !== $pin->sha256) {
                throw new CatalogContractViolation('Descriptor/payload/version pin mismatch.');
            }
            $snapshot = new CatalogSnapshot(new CatalogSnapshotDescriptor($type, $descriptor->schema_version,
                $descriptor->owner, $descriptor->version, $descriptor->content_schema_version, $descriptor->canonicalization,
                $descriptor->sha256, $descriptor->size_bytes, $descriptor->artifact_path), $this->arrayValue($payload));
            $this->integrity->assertValid($snapshot);
            $catalogs[$key] = $snapshot;
        }
        if ($manifest->resolution !== null) {
            $roots[] = 'source-proposal-contract-v1.manifest.json';
        }
        $trusted = $this->contracts->files(array_values(array_unique($roots)));
        foreach ($trusted as $name => $content) {
            if (($artifacts['contracts/'.$name] ?? null) !== $content) {
                throw new CatalogContractViolation('Delivered schema/contract differs from independent pin: '.$name);
            }
        }
        foreach ($artifacts as $name => $content) {
            if (str_starts_with($name, 'contracts/') && ! isset($trusted[substr($name, 10)])) {
                throw new CatalogContractViolation('Untrusted extra contract artifact.');
            }
        }
        $delivery = new VerifiedAtlasDelivery($expectedSha256, $bytes, $manifest, $artifacts, $catalogs);
        $this->resolutions->verify($delivery);

        return $delivery;
    }

    /** Preserve empty JSON objects through the legacy array-based snapshot DTO. */
    private function arrayValue(mixed $value): mixed
    {
        if (is_object($value) && get_object_vars($value) !== []) {
            return array_map($this->arrayValue(...), get_object_vars($value));
        }
        if (is_array($value)) {
            return array_map($this->arrayValue(...), $value);
        }

        return $value;
    }
}
