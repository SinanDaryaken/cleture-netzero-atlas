<?php

namespace App\Infrastructure\Candidate;

use App\Application\Contracts\LicenseSnapshotLoader;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Candidate\LicenseSnapshot;
use Illuminate\Filesystem\FilesystemManager;

final readonly class LaravelLicenseSnapshotLoader implements LicenseSnapshotLoader
{
    public function __construct(private FilesystemManager $filesystems, private string $disk) {}

    public function load(string $descriptorPath, string $descriptorSha256, array $source): LicenseSnapshot
    {
        if (preg_match('#^licenses/sha256/[a-f0-9]{64}\.json$#', $descriptorPath) !== 1
            || $descriptorPath !== "licenses/sha256/{$descriptorSha256}.json") {
            throw new CandidateContractViolation('License descriptor requires a content-addressed path and exact SHA-256.');
        }
        $filesystem = $this->filesystems->disk($this->disk);
        $bytes = $filesystem->get($descriptorPath);
        if (! is_string($bytes) || ! hash_equals($descriptorSha256, hash('sha256', $bytes))) {
            throw new CandidateContractViolation('License descriptor checksum mismatch.');
        }
        $descriptor = json_decode($bytes, true, 512, JSON_THROW_ON_ERROR);
        $keys = is_array($descriptor) ? array_keys($descriptor) : [];
        sort($keys);
        if ($keys !== ['license', 'schema_version', 'source', 'terms_object_key', 'terms_size_bytes']
            || $descriptor['schema_version'] !== 'atlas-license-evidence/v1'
            || ! is_array($descriptor['source']) || $descriptor['source'] != $source
            || ! is_int($descriptor['terms_size_bytes']) || $descriptor['terms_size_bytes'] < 1) {
            throw new CandidateContractViolation('License descriptor shape or source binding is invalid.');
        }
        $license = $descriptor['license'];
        $keys = is_array($license) ? array_keys($license) : [];
        sort($keys);
        if ($keys !== ['attribution', 'identifier', 'name', 'retrieved_at', 'source_uri', 'terms_sha256']) {
            throw new CandidateContractViolation('License metadata is incomplete.');
        }
        foreach (['attribution', 'identifier', 'name', 'retrieved_at', 'source_uri', 'terms_sha256'] as $key) {
            if (! is_string($license[$key]) || trim($license[$key]) === '') {
                throw new CandidateContractViolation('License metadata must contain explicit evidence.');
            }
        }
        if (preg_match('/^[a-f0-9]{64}$/', $license['terms_sha256']) !== 1
            || ! filter_var($license['source_uri'], FILTER_VALIDATE_URL)
            || ! in_array(parse_url($license['source_uri'], PHP_URL_SCHEME), ['http', 'https'], true)
            || preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/', $license['retrieved_at']) !== 1
            || $descriptor['terms_object_key'] !== 'licenses/sha256/'.$license['terms_sha256'].'.terms') {
            throw new CandidateContractViolation('Invalid license terms identity, URI or timestamp.');
        }
        try {
            new \DateTimeImmutable($license['retrieved_at']);
            $dateErrors = \DateTimeImmutable::getLastErrors();
            if ($dateErrors !== false && ($dateErrors['warning_count'] > 0 || $dateErrors['error_count'] > 0)) {
                throw new \InvalidArgumentException('Invalid calendar date.');
            }
        } catch (\Exception $exception) {
            throw new CandidateContractViolation('Invalid license retrieval timestamp.', previous: $exception);
        }
        $stream = $filesystem->readStream($descriptor['terms_object_key']);
        if (! is_resource($stream)) {
            throw new CandidateContractViolation('License terms are unavailable.');
        }
        try {
            $hash = hash_init('sha256');
            $size = hash_update_stream($hash, $stream);
            if ($size !== $descriptor['terms_size_bytes'] || ! hash_equals($license['terms_sha256'], hash_final($hash))) {
                throw new CandidateContractViolation('License terms exact bytes do not match the descriptor.');
            }
        } finally {
            fclose($stream);
        }

        return new LicenseSnapshot($license, $source, $descriptorSha256);
    }
}
