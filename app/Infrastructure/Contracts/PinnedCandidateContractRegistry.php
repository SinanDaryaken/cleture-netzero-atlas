<?php

namespace App\Infrastructure\Contracts;

use App\Application\Contracts\CandidateContractRegistry;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\CandidateContractDocument;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use JsonException;

final class PinnedCandidateContractRegistry implements CandidateContractRegistry
{
    /** @var array<string, mixed>|null */
    private ?array $manifest = null;

    public function __construct(private readonly string $manifestPath) {}

    public function get(CandidateContract $contract): CandidateContractDocument
    {
        $manifest = $this->manifest();

        foreach ($manifest['contracts'] as $entry) {
            if (! is_array($entry) || ($entry['name'] ?? null) !== $contract->value) {
                continue;
            }

            return $this->document($contract, $manifest, $entry);
        }

        throw new CandidateContractViolation("Candidate contract {$contract->value} is not pinned.");
    }

    public function missingPackageRecordContracts(): array
    {
        $missing = $this->manifest()['missing_package_record_contracts'] ?? null;

        if (! is_array($missing)) {
            throw new CandidateContractViolation('Pinned candidate contract manifest has an invalid package readiness gate.');
        }

        foreach ($missing as $name) {
            if (! is_string($name) || $name === '') {
                throw new CandidateContractViolation('Pinned candidate contract manifest has an invalid package readiness gate.');
            }
        }

        return array_values($missing);
    }

    public function assertPackageBuildReady(): void
    {
        $missing = $this->missingPackageRecordContracts();

        if ($missing !== []) {
            throw new CandidateContractViolation(
                'Candidate package build is blocked by missing record contracts: '.implode(', ', $missing).'.',
            );
        }

        foreach (CandidateContract::cases() as $contract) {
            $this->get($contract);
        }

        $manifest = $this->manifest();

        if (($manifest['snapshot_version'] ?? null) === '2.0.0') {
            $this->assertV2ArchivePolicy($manifest);
        }
    }

    /**
     * @return array<string, mixed>
     */
    private function manifest(): array
    {
        if ($this->manifest !== null) {
            return $this->manifest;
        }

        $contents = @file_get_contents($this->manifestPath);

        if (! is_string($contents)) {
            throw new CandidateContractViolation('Pinned candidate contract manifest cannot be read.');
        }

        try {
            $manifest = json_decode($contents, true, flags: JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new CandidateContractViolation('Pinned candidate contract manifest is not valid JSON.', previous: $exception);
        }

        if (! is_array($manifest)
            || ! in_array($manifest['snapshot_version'] ?? null, ['1.0.0', '2.0.0'], true)
            || ($manifest['owner'] ?? null) !== 'cleture-netzero-admin'
            || ! is_string($manifest['upstream_repository'] ?? null)
            || ! preg_match('/^[a-f0-9]{40,64}$/', $manifest['upstream_commit'] ?? '')
            || ! is_array($manifest['contracts'] ?? null)
        ) {
            throw new CandidateContractViolation('Pinned candidate contract manifest identity is invalid.');
        }

        if ($manifest['snapshot_version'] === '2.0.0') {
            $this->assertUpstreamManifest($manifest);
        }

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
            throw new CandidateContractViolation('Pinned candidate V2 upstream manifest identity is invalid.');
        }

        $contents = @file_get_contents(dirname($this->manifestPath).DIRECTORY_SEPARATOR.$identity['path']);

        if (! is_string($contents) || ! hash_equals($identity['sha256'], hash('sha256', $contents))) {
            throw new CandidateContractViolation('Pinned candidate V2 upstream manifest failed integrity validation.');
        }

        try {
            $upstream = json_decode($contents, true, flags: JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new CandidateContractViolation(
                'Pinned candidate V2 upstream manifest is not valid JSON.',
                previous: $exception,
            );
        }

        if (! is_array($upstream)
            || ($upstream['snapshot_version'] ?? null) !== '2.0.0'
            || ($upstream['owner_repository'] ?? null) !== $manifest['upstream_repository']
            || ! is_array($upstream['contracts'] ?? null)
            || count($upstream['contracts']) !== count(CandidateContract::cases())
            || count($manifest['contracts']) !== count(CandidateContract::cases())
            || ($upstream['archive_members'] ?? null) !== ($manifest['archive_members'] ?? null)
        ) {
            throw new CandidateContractViolation('Pinned candidate V2 upstream manifest contract is invalid.');
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
                || ($local['version'] ?? null) !== ($entry['version'] ?? null)
                || ($local['path'] ?? null) !== ($entry['path'] ?? null)
                || ($local['schema_id'] ?? null) !== ($entry['schema_id'] ?? null)
                || ($local['sha256'] ?? null) !== ($entry['sha256'] ?? null)
                || ($local['upstream_sha256'] ?? null) !== ($entry['sha256'] ?? null)
            ) {
                throw new CandidateContractViolation('Pinned candidate V2 schemas diverge from the upstream manifest.');
            }
        }
    }

    /** @param array<string, mixed> $manifest */
    private function assertV2ArchivePolicy(array $manifest): void
    {
        $members = $manifest['archive_members'] ?? null;

        if (! is_array($members) || count($members) !== 4) {
            throw new CandidateContractViolation('Pinned candidate V2 archive policy is invalid.');
        }

        $policies = [];

        foreach ($members as $member) {
            if (! is_array($member)
                || ! is_string($member['path'] ?? null)
                || ! is_string($member['contract'] ?? null)
                || ! is_string($member['record_policy'] ?? null)
            ) {
                throw new CandidateContractViolation('Pinned candidate V2 archive policy is invalid.');
            }

            $policies[$member['path']] = [$member['contract'], $member['record_policy']];
        }

        if ($policies !== [
            'entities.ndjson' => ['candidate_entity_record', 'records_allowed'],
            'relationships.ndjson' => ['candidate_relationship_record', 'records_forbidden'],
            'findings.ndjson' => ['candidate_finding_record', 'records_allowed_or_empty'],
            'source-diff.ndjson' => ['candidate_source_diff_record', 'records_allowed_or_empty'],
        ]) {
            throw new CandidateContractViolation('Pinned candidate V2 archive policy is invalid.');
        }
    }

    /**
     * @param  array<string, mixed>  $manifest
     * @param  array<string, mixed>  $entry
     */
    private function document(
        CandidateContract $contract,
        array $manifest,
        array $entry,
    ): CandidateContractDocument {
        $path = $entry['path'] ?? null;

        if (! is_string($path) || $path === '' || basename($path) !== $path) {
            throw new CandidateContractViolation("Pinned candidate contract {$contract->value} has an invalid path.");
        }

        $contents = @file_get_contents(dirname($this->manifestPath).DIRECTORY_SEPARATOR.$path);

        if (! is_string($contents)) {
            throw new CandidateContractViolation("Pinned candidate contract {$contract->value} cannot be read.");
        }

        try {
            $schema = json_decode($contents, true, flags: JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new CandidateContractViolation(
                "Pinned candidate contract {$contract->value} is not valid JSON.",
                previous: $exception,
            );
        }

        if (! is_array($schema) || ($schema['$id'] ?? null) !== ($entry['schema_id'] ?? null)) {
            throw new CandidateContractViolation("Pinned candidate contract {$contract->value} schema identity is invalid.");
        }

        try {
            return new CandidateContractDocument(
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
        } catch (\InvalidArgumentException $exception) {
            throw new CandidateContractViolation(
                "Pinned candidate contract {$contract->value} failed integrity validation.",
                previous: $exception,
            );
        }
    }

    /**
     * @param  array<string, mixed>  $entry
     */
    private function requiredString(array $entry, string $key, CandidateContract $contract): string
    {
        $value = $entry[$key] ?? null;

        if (! is_string($value) || $value === '') {
            throw new CandidateContractViolation(
                "Pinned candidate contract {$contract->value} is missing {$key}.",
            );
        }

        return $value;
    }
}
