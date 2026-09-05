<?php

namespace App\Infrastructure\Contracts;

use App\Application\Contracts\CatalogContractRegistry;
use App\Domain\Catalog\CatalogContract;
use App\Domain\Catalog\CatalogContractDocument;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use InvalidArgumentException;
use JsonException;

final class PinnedCatalogContractRegistry implements CatalogContractRegistry
{
    /** @var array<string, mixed>|null */
    private ?array $manifest = null;

    public function __construct(private readonly string $manifestPath) {}

    public function get(CatalogContract $contract): CatalogContractDocument
    {
        $manifest = $this->manifest();

        foreach ($manifest['contracts'] as $entry) {
            if (! is_array($entry) || ($entry['name'] ?? null) !== $contract->value) {
                continue;
            }

            return $this->document($contract, $manifest, $entry);
        }

        throw new CatalogContractViolation("Catalog contract {$contract->value} is not pinned.");
    }

    /** @return array<string, mixed> */
    private function manifest(): array
    {
        if ($this->manifest !== null) {
            return $this->manifest;
        }

        $manifest = $this->decodeFile($this->manifestPath, 'Pinned catalog contract manifest');

        if (($manifest['snapshot_version'] ?? null) !== '1.0.0'
            || ($manifest['owner'] ?? null) !== 'cleture-netzero-admin'
            || ($manifest['upstream_repository'] ?? null) !== 'cleture-netzero-admin'
            || ! preg_match('/^[a-f0-9]{40,64}$/', $manifest['upstream_commit'] ?? '')
            || ! is_array($manifest['contracts'] ?? null)
            || count($manifest['contracts']) !== count(CatalogContract::cases())
        ) {
            throw new CatalogContractViolation('Pinned catalog contract manifest identity is invalid.');
        }

        $this->assertUpstreamManifest($manifest);

        return $this->manifest = $manifest;
    }

    /** @param array<string, mixed> $manifest */
    private function assertUpstreamManifest(array $manifest): void
    {
        $identity = $manifest['upstream_manifest'] ?? null;

        if (! is_array($identity)
            || ! is_string($identity['path'] ?? null)
            || basename($identity['path']) !== $identity['path']
            || ! preg_match('/^[a-f0-9]{64}$/', $identity['sha256'] ?? '')
            || ! preg_match('/^[a-f0-9]{40,64}$/', $identity['upstream_git_blob'] ?? '')
            || ! is_string($identity['upstream_path'] ?? null)
        ) {
            throw new CatalogContractViolation('Pinned catalog upstream manifest identity is invalid.');
        }

        $path = dirname($this->manifestPath).DIRECTORY_SEPARATOR.$identity['path'];
        $contents = @file_get_contents($path);

        if (! is_string($contents) || ! hash_equals($identity['sha256'], hash('sha256', $contents))) {
            throw new CatalogContractViolation('Pinned catalog upstream manifest failed integrity validation.');
        }

        try {
            $upstream = json_decode($contents, true, flags: JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new CatalogContractViolation('Pinned catalog upstream manifest is not valid JSON.', previous: $exception);
        }

        if (! is_array($upstream)
            || ($upstream['snapshot_version'] ?? null) !== $manifest['snapshot_version']
            || ($upstream['owner_repository'] ?? null) !== $manifest['upstream_repository']
            || ! is_array($upstream['contracts'] ?? null)
            || count($upstream['contracts']) !== count(CatalogContract::cases())
        ) {
            throw new CatalogContractViolation('Pinned catalog upstream manifest contract is invalid.');
        }

        $localContracts = [];

        foreach ($manifest['contracts'] as $entry) {
            if (is_array($entry) && is_string($entry['name'] ?? null)) {
                $localContracts[$entry['name']] = $entry;
            }
        }

        foreach ($upstream['contracts'] as $entry) {
            $name = is_array($entry) ? ($entry['name'] ?? null) : null;
            $local = is_string($name) ? ($localContracts[$name] ?? null) : null;

            if (! is_array($entry)
                || ! is_array($local)
                || ($local['path'] ?? null) !== ($entry['path'] ?? null)
                || ($local['schema_id'] ?? null) !== ($entry['schema_id'] ?? null)
                || ($local['sha256'] ?? null) !== ($entry['sha256'] ?? null)
            ) {
                throw new CatalogContractViolation('Pinned catalog schemas diverge from the upstream manifest.');
            }
        }
    }

    /**
     * @param  array<string, mixed>  $manifest
     * @param  array<string, mixed>  $entry
     */
    private function document(
        CatalogContract $contract,
        array $manifest,
        array $entry,
    ): CatalogContractDocument {
        $path = $entry['path'] ?? null;

        if (! is_string($path) || basename($path) !== $path) {
            throw new CatalogContractViolation("Pinned catalog contract {$contract->value} has an invalid path.");
        }

        $contents = @file_get_contents(dirname($this->manifestPath).DIRECTORY_SEPARATOR.$path);

        if (! is_string($contents)) {
            throw new CatalogContractViolation("Pinned catalog contract {$contract->value} cannot be read.");
        }

        try {
            $schema = json_decode($contents, true, flags: JSON_THROW_ON_ERROR);

            if (! is_array($schema) || ($schema['$id'] ?? null) !== ($entry['schema_id'] ?? null)) {
                throw new CatalogContractViolation("Pinned catalog contract {$contract->value} schema identity is invalid.");
            }

            return new CatalogContractDocument(
                contract: $contract,
                version: $this->requiredString($entry, 'version', $contract),
                schemaId: $this->requiredString($entry, 'schema_id', $contract),
                sha256: $this->requiredString($entry, 'sha256', $contract),
                contents: $contents,
                owner: $manifest['owner'],
                upstreamRepository: $manifest['upstream_repository'],
                upstreamCommit: $manifest['upstream_commit'],
                upstreamGitBlob: $this->requiredString($entry, 'upstream_git_blob', $contract),
                upstreamPath: $this->requiredString($entry, 'upstream_path', $contract),
            );
        } catch (JsonException|InvalidArgumentException $exception) {
            throw new CatalogContractViolation(
                "Pinned catalog contract {$contract->value} failed integrity validation.",
                previous: $exception,
            );
        }
    }

    /** @return array<string, mixed> */
    private function decodeFile(string $path, string $label): array
    {
        $contents = @file_get_contents($path);

        if (! is_string($contents)) {
            throw new CatalogContractViolation("{$label} cannot be read.");
        }

        try {
            $decoded = json_decode($contents, true, flags: JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new CatalogContractViolation("{$label} is not valid JSON.", previous: $exception);
        }

        if (! is_array($decoded)) {
            throw new CatalogContractViolation("{$label} must be a JSON object.");
        }

        return $decoded;
    }

    /** @param array<string, mixed> $entry */
    private function requiredString(array $entry, string $key, CatalogContract $contract): string
    {
        $value = $entry[$key] ?? null;

        if (! is_string($value) || $value === '') {
            throw new CatalogContractViolation("Pinned catalog contract {$contract->value} is missing {$key}.");
        }

        return $value;
    }
}
