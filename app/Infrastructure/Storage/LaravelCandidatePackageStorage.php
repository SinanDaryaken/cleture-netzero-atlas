<?php

namespace App\Infrastructure\Storage;

use App\Application\Contracts\CandidatePackageStorage;
use App\Domain\Candidate\CandidatePackageBuild;
use App\Domain\Candidate\StoredCandidatePackage;
use Illuminate\Filesystem\FilesystemAdapter;
use Illuminate\Filesystem\FilesystemManager;
use RuntimeException;

final readonly class LaravelCandidatePackageStorage implements CandidatePackageStorage
{
    public function __construct(
        private FilesystemManager $filesystems,
        private string $disk,
    ) {}

    public function store(CandidatePackageBuild $package): StoredCandidatePackage
    {
        $filesystem = $this->filesystems->disk($this->disk);
        $archive = $package->artifact;
        $manifestBytes = $package->canonicalManifestJson;
        $manifestSha256 = hash('sha256', $manifestBytes);
        $manifestObjectKey = "manifests/sha256/{$manifestSha256}.json";
        $archiveAlreadyExisted = $filesystem->exists($archive->objectKey);
        $manifestAlreadyExisted = $filesystem->exists($manifestObjectKey);

        if (! $archiveAlreadyExisted) {
            $this->putFile($filesystem, $archive->objectKey, $archive->temporaryPath);
        }

        if (! $manifestAlreadyExisted && ! $filesystem->put($manifestObjectKey, $manifestBytes)) {
            throw new RuntimeException('Candidate package manifest could not be written to object storage.');
        }

        $this->assertStoredIdentity($filesystem, $archive->objectKey, $archive->sizeBytes, $archive->sha256);
        $this->assertStoredIdentity($filesystem, $manifestObjectKey, strlen($manifestBytes), $manifestSha256);

        return new StoredCandidatePackage(
            disk: $this->disk,
            archiveObjectKey: $archive->objectKey,
            archiveSha256: $archive->sha256,
            archiveSize: $archive->sizeBytes,
            manifestObjectKey: $manifestObjectKey,
            manifestSha256: $manifestSha256,
            manifestSize: strlen($manifestBytes),
            archiveAlreadyExisted: $archiveAlreadyExisted,
            manifestAlreadyExisted: $manifestAlreadyExisted,
        );
    }

    private function putFile(FilesystemAdapter $filesystem, string $objectKey, string $path): void
    {
        $stream = fopen($path, 'rb');

        if ($stream === false) {
            throw new RuntimeException('Candidate package archive could not be opened for object storage.');
        }

        try {
            if (! $filesystem->put($objectKey, $stream)) {
                throw new RuntimeException('Candidate package archive could not be written to object storage.');
            }
        } finally {
            fclose($stream);
        }
    }

    private function assertStoredIdentity(
        FilesystemAdapter $filesystem,
        string $objectKey,
        int $expectedSize,
        string $expectedSha256,
    ): void {
        if ($filesystem->size($objectKey) !== $expectedSize) {
            throw new RuntimeException("Stored candidate object {$objectKey} size verification failed.");
        }

        $stream = $filesystem->readStream($objectKey);

        if ($stream === false) {
            throw new RuntimeException("Stored candidate object {$objectKey} could not be read for verification.");
        }

        try {
            $hash = hash_init('sha256');
            hash_update_stream($hash, $stream);
            $actualSha256 = hash_final($hash);
        } finally {
            fclose($stream);
        }

        if (! hash_equals($expectedSha256, $actualSha256)) {
            throw new RuntimeException("Stored candidate object {$objectKey} checksum verification failed.");
        }
    }
}
