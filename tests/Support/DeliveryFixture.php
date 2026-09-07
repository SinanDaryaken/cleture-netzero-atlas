<?php

namespace Tests\Support;

use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use App\Infrastructure\Contracts\PinnedDeliveryContracts;

/** Synthetic fixtures, authored and hashed independently in Python. */
final class DeliveryFixture
{
    public array $files = [];

    public array $catalogs = [];

    public ?array $resolution = null;

    public function __construct(?string $resolutionType = null)
    {
        $payloads = json_decode(file_get_contents(base_path('tests/fixtures/atlas-delivery/catalogs.json')), true, flags: JSON_THROW_ON_ERROR);
        foreach ($payloads as $type => $payload) {
            $this->catalog($type, $payload);
        }
        $roots = array_keys(PinnedDeliveryContracts::ROOTS);
        if ($resolutionType === null) {
            $roots = array_values(array_diff($roots, ['source-proposal-contract-v1.manifest.json']));
        } else {
            $cases = json_decode(file_get_contents(base_path('tests/fixtures/atlas-delivery/resolutions.json')), true, flags: JSON_THROW_ON_ERROR);
            $case = $cases[$resolutionType];
            $this->resolution = $case['pin'];
            $this->files = $case['artifacts'];
            // Restore catalog artifacts after adding the precomputed authority bytes.
            foreach ($payloads as $type => $payload) {
                $this->catalog($type, $payload);
            }
            if ($case['target'] !== null) {
                $this->catalog('unit', $case['target']);
            }
        }
        foreach ((new PinnedDeliveryContracts(base_path('resources/contracts/netzero-admin/delivery-v1')))->files($roots) as $name => $bytes) {
            $this->files['contracts/'.$name] = $bytes;
        }
    }

    public function catalog(string $type, array $payload): void
    {
        $bytes = self::json($payload);
        $hash = hash('sha256', $bytes);
        $path = 'atlas-catalog-snapshots/'.$type.'/sha256/'.$hash.'.json';
        $version = $type === 'unit' ? $payload['release']['version'] : 'sha256:'.$hash;
        $descriptor = ['schema_version' => match ($type) {
            'unit' => 'atlas-catalog-snapshot/v2', 'geography' => 'atlas-catalog-snapshot/v1',
            'currency' => 'netzero-currency-snapshot-descriptor/v1', default => 'netzero-review-catalog-descriptor/v1',
        }, 'owner' => 'NetZeroAdmin', 'catalog' => $type, 'version' => $version, 'content_schema_version' => $payload['schema_version'],
            'canonicalization' => 'netzero-sorted-json-v1', 'sha256' => $hash, 'size_bytes' => strlen($bytes), 'artifact_path' => $path];
        $this->files[$path] = $bytes;
        $this->files[$path.'.manifest.json'] = self::json($descriptor);
        $this->catalogs[$type.':'.$hash] = ['catalog' => $type, 'version' => $version, 'sha256' => $hash, 'artifact_name' => $path, 'descriptor_name' => $path.'.manifest.json'];
    }

    /** @return array{hash: string, objects: array<string, string>, manifest: array} */
    public function package(?callable $mutate = null): array
    {
        $artifacts = [];
        $objects = [];
        foreach ($this->files as $name => $bytes) {
            $hash = hash('sha256', $bytes);
            $path = 'objects/sha256/'.$hash;
            $objects[$path] = $bytes;
            $artifacts[] = ['name' => $name, 'object_path' => $path, 'sha256' => $hash, 'size_bytes' => strlen($bytes)];
        }
        $manifest = ['schema_version' => 'netzero-atlas-delivery/v1', 'owner' => 'NetZeroAdmin',
            'policy' => ['consumer_must_recheck_current' => true, 'source_scope_required' => true, 'automatic_mapping_allowed' => false, 'publish_allowed' => false],
            'resolution' => $this->resolution, 'catalogs' => array_values($this->catalogs), 'artifacts' => $artifacts];
        if ($mutate !== null) {
            $manifest = $mutate($manifest);
        }
        $objects['manifest.json'] = self::json($manifest);

        return ['hash' => hash('sha256', $objects['manifest.json']), 'objects' => $objects, 'manifest' => $manifest];
    }

    public static function read(array $objects): \Closure
    {
        return static function (string $path, int $limit) use ($objects): string {
            return $objects[$path] ?? throw new CatalogContractViolation('Missing fixture artifact.');
        };
    }

    /** Independent test serialization, not the production canonicalizer. */
    public static function json(mixed $value): string
    {
        $sort = function (mixed $item) use (&$sort): mixed {
            if (is_object($item)) {
                $vars = get_object_vars($item);
                ksort($vars, SORT_STRING);

                return (object) array_map($sort, $vars);
            }
            if (is_array($item)) {
                if (! array_is_list($item)) {
                    ksort($item, SORT_STRING);
                }

                return array_map($sort, $item);
            }

            return $item;
        };

        return json_encode($sort($value), JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    }
}
