<?php

namespace App\Infrastructure\Catalog;

use App\Application\Contracts\CatalogSchemaValidator;
use App\Application\Contracts\CatalogSnapshotLoader;
use App\Domain\Catalog\CatalogContract;
use App\Domain\Catalog\CatalogSnapshot;
use App\Domain\Catalog\CatalogSnapshotDescriptor;
use App\Domain\Catalog\CatalogSnapshotIntegrity;
use App\Domain\Catalog\CatalogType;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use Illuminate\Filesystem\FilesystemManager;
use InvalidArgumentException;
use JsonException;
use Throwable;
use TypeError;
use ValueError;

final class LaravelCatalogSnapshotLoader implements CatalogSnapshotLoader
{
    /** @var array<string, CatalogSnapshot> */
    private array $loadedSnapshots = [];

    /**
     * @param  array<string, array{descriptor_path: string, descriptor_sha256: string}>  $snapshotConfigurations
     */
    public function __construct(
        private readonly FilesystemManager $filesystems,
        private readonly CatalogSchemaValidator $schemaValidator,
        private readonly CatalogSnapshotIntegrity $integrity,
        private readonly string $disk,
        private readonly array $snapshotConfigurations,
    ) {}

    public function load(CatalogType $catalog): CatalogSnapshot
    {
        if (isset($this->loadedSnapshots[$catalog->value])) {
            return $this->loadedSnapshots[$catalog->value];
        }

        $configuration = $this->configuration($catalog);
        $filesystem = $this->filesystems->disk($this->disk);

        try {
            $descriptorBytes = $filesystem->get($configuration['descriptor_path']);
        } catch (Throwable $exception) {
            throw new CatalogContractViolation(
                "The pinned {$catalog->value} catalog descriptor could not be read.",
                previous: $exception,
            );
        }

        if (! hash_equals($configuration['descriptor_sha256'], hash('sha256', $descriptorBytes))) {
            throw new CatalogContractViolation(
                "The pinned {$catalog->value} catalog descriptor checksum does not match.",
            );
        }

        $descriptorRecord = $this->decode($descriptorBytes, "{$catalog->value} catalog descriptor");
        $this->schemaValidator->assertValid(CatalogContract::Descriptor, $descriptorRecord);
        $descriptor = $this->descriptor($catalog, $descriptorRecord);

        try {
            $payloadBytes = $filesystem->get($descriptor->artifactPath);
        } catch (Throwable $exception) {
            throw new CatalogContractViolation(
                "The pinned {$catalog->value} catalog payload could not be read.",
                previous: $exception,
            );
        }

        if (strlen($payloadBytes) !== $descriptor->sizeBytes
            || ! hash_equals($descriptor->sha256, hash('sha256', $payloadBytes))
        ) {
            throw new CatalogContractViolation(
                "The pinned {$catalog->value} catalog payload identity does not match its descriptor.",
            );
        }

        $payload = $this->decode($payloadBytes, "{$catalog->value} catalog payload");
        $this->schemaValidator->assertValid($catalog->contract(), $payload);
        $snapshot = new CatalogSnapshot($descriptor, $payload);
        $this->integrity->assertValid($snapshot);

        return $this->loadedSnapshots[$catalog->value] = $snapshot;
    }

    /** @return array{descriptor_path: string, descriptor_sha256: string} */
    private function configuration(CatalogType $catalog): array
    {
        $configuration = $this->snapshotConfigurations[$catalog->value] ?? null;

        if (! is_array($configuration)
            || ! is_string($configuration['descriptor_path'] ?? null)
            || preg_match('#^atlas-catalog-snapshots/(unit|geography)/sha256/[a-f0-9]{64}\.json\.manifest\.json$#', $configuration['descriptor_path']) !== 1
            || ! str_contains($configuration['descriptor_path'], "/{$catalog->value}/")
            || ! is_string($configuration['descriptor_sha256'] ?? null)
            || ! preg_match('/^[a-f0-9]{64}$/', $configuration['descriptor_sha256'])
        ) {
            throw new CatalogContractViolation("The {$catalog->value} catalog snapshot configuration is invalid.");
        }

        return $configuration;
    }

    /** @param array<string, mixed> $record */
    private function descriptor(CatalogType $catalog, array $record): CatalogSnapshotDescriptor
    {
        if (($record['catalog'] ?? null) !== $catalog->value) {
            throw new CatalogContractViolation("Catalog descriptor does not describe {$catalog->value}.");
        }

        try {
            return new CatalogSnapshotDescriptor(
                catalog: $catalog,
                schemaVersion: $record['schema_version'],
                owner: $record['owner'],
                version: $record['version'],
                contentSchemaVersion: $record['content_schema_version'],
                canonicalization: $record['canonicalization'],
                sha256: $record['sha256'],
                sizeBytes: $record['size_bytes'],
                artifactPath: $record['artifact_path'],
            );
        } catch (InvalidArgumentException|TypeError|ValueError $exception) {
            throw new CatalogContractViolation('Catalog descriptor identity is invalid.', previous: $exception);
        }
    }

    /** @return array<string, mixed> */
    private function decode(string $bytes, string $label): array
    {
        try {
            $record = json_decode($bytes, true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new CatalogContractViolation("The {$label} is not valid JSON.", previous: $exception);
        }

        if (! is_array($record) || array_is_list($record)) {
            throw new CatalogContractViolation("The {$label} must be a JSON object.");
        }

        return $record;
    }
}
