<?php

namespace Tests\Unit\Infrastructure\Storage;

use App\Domain\Candidate\CandidatePackageArtifact;
use App\Domain\Candidate\CandidatePackageBuild;
use App\Infrastructure\Storage\LaravelCandidatePackageStorage;
use Illuminate\Filesystem\FilesystemManager;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class LaravelCandidatePackageStorageTest extends TestCase
{
    public function test_stores_and_reuses_verified_content_addressed_archive_and_manifest(): void
    {
        Storage::fake('candidate_test');
        $temporaryPath = tempnam(sys_get_temp_dir(), 'atlas-storage-test-');
        file_put_contents($temporaryPath, 'immutable-archive');
        $archiveSha256 = hash('sha256', 'immutable-archive');
        $package = new CandidatePackageBuild(
            artifact: new CandidatePackageArtifact(
                temporaryPath: $temporaryPath,
                objectKey: "sha256/{$archiveSha256}.zip",
                sha256: $archiveSha256,
                sizeBytes: strlen('immutable-archive'),
            ),
            manifest: ['schema_version' => '2.0.0'],
            canonicalManifestJson: '{"schema_version":"2.0.0"}',
        );
        $storage = new LaravelCandidatePackageStorage(
            app(FilesystemManager::class),
            'candidate_test',
        );

        $first = $storage->store($package);
        $second = $storage->store($package);

        try {
            Storage::disk('candidate_test')->assertExists($first->archiveObjectKey);
            Storage::disk('candidate_test')->assertExists($first->manifestObjectKey);
            $this->assertFalse($first->archiveAlreadyExisted);
            $this->assertFalse($first->manifestAlreadyExisted);
            $this->assertTrue($second->archiveAlreadyExisted);
            $this->assertTrue($second->manifestAlreadyExisted);
            $this->assertSame('immutable-archive', Storage::disk('candidate_test')->get($first->archiveObjectKey));
            $this->assertSame(
                $package->canonicalManifestJson,
                Storage::disk('candidate_test')->get($first->manifestObjectKey),
            );
        } finally {
            unlink($temporaryPath);
        }
    }
}
