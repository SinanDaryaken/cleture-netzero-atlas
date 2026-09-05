<?php

namespace Tests\Integration;

use App\Application\Candidate\PrepareCandidatePackage;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use Illuminate\Foundation\Testing\DatabaseMigrations;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use PHPUnit\Framework\Attributes\Group;
use Symfony\Component\Process\Process;
use Tests\Support\CandidatePipelineFixture;
use Tests\TestCase;

#[Group('integration')]
final class CandidatePackagePipelineTest extends TestCase
{
    use DatabaseMigrations;

    protected function beforeRefreshingDatabase(): void
    {
        if (config('database.default') !== 'pgsql' || ! str_starts_with(config('database.connections.pgsql.database'), 'atlas_validation_test_')) {
            $this->markTestSkipped('Requires a dedicated atlas_validation_test_* PostgreSQL database.');
        }
    }

    public function test_concurrent_builds_share_verified_package_and_validation_evidence_on_postgres_and_minio(): void
    {
        $bucket = 'atlas-validation-test-'.bin2hex(random_bytes(8));
        foreach (['atlas_processing', 'atlas_catalogs', 'atlas_candidates'] as $disk) {
            config(["filesystems.disks.{$disk}.bucket" => $bucket]);
            Storage::forgetDisk($disk);
        }
        $client = Storage::disk('atlas_candidates')->getClient();
        $client->createBucket(['Bucket' => $bucket]);
        $paths = $children = [];
        try {
            $plan = CandidatePipelineFixture::seed();
            $path = tempnam(sys_get_temp_dir(), 'atlas-concurrent-test-');
            $paths[] = $path;
            file_put_contents($path, json_encode(['plan' => $plan, 'catalogs' => config('atlas.catalogs.snapshots'), 'bucket' => $bucket], JSON_THROW_ON_ERROR));
            DB::purge();
            for ($i = 0; $i < 2; $i++) {
                $process = new Process([PHP_BINARY, base_path('tests/Support/run-candidate-build.php'), $path], base_path(), ['APP_ENV' => 'testing']);
                $process->start();
                $children[] = $process;
            }
            foreach ($children as $process) {
                $this->assertSame(0, $process->wait(), $process->getErrorOutput());
            }
            DB::purge();
            $first = json_decode($children[0]->getOutput(), true, 512, JSON_THROW_ON_ERROR);
            $second = json_decode($children[1]->getOutput(), true, 512, JSON_THROW_ON_ERROR);
            $this->assertSame($first, $second);
            $this->assertDatabaseCount('candidate_packages', 1);
            $this->assertDatabaseCount('candidate_package_attempts', 1);
            $this->assertDatabaseCount('candidate_validation_runs', 1);
            $retry = app(PrepareCandidatePackage::class)->handle($plan, 'atlas_candidates');
            $this->assertTrue($retry->package->alreadyExisted);
            $this->assertSame($first['package'], $retry->package->packageId);

            $plan['previous_package_id'] = $first['package'];
            $next = app(PrepareCandidatePackage::class)->handle($plan, 'atlas_candidates');
            $manifest = json_decode(Storage::disk('atlas_candidates')->get($next->package->storage->manifestObjectKey), true);
            $this->assertSame(1, $manifest['source_diff_summary']['unchanged']);

            // Deliberately corrupt only the isolated test bucket's previous archive.
            Storage::disk('atlas_candidates')->put($retry->package->storage->archiveObjectKey, 'corrupt');
            try {
                app(PrepareCandidatePackage::class)->handle($plan, 'atlas_candidates');
                $this->fail('Corrupt previous archive was accepted.');
            } catch (CandidateContractViolation $exception) {
                $this->assertStringContainsString('Previous archive checksum', $exception->getMessage());
            }
        } finally {
            foreach ($children as $process) {
                if ($process->isRunning()) {
                    $process->stop();
                }
            }
            foreach ($paths as $path) {
                unlink($path);
            }
            // Bucket name is generated here and never points at application buckets.
            if (preg_match('/^atlas-validation-test-[a-f0-9]{16}$/', $bucket) !== 1) {
                throw new \LogicException('Unsafe test bucket cleanup target.');
            }
            foreach ($client->getPaginator('ListObjectsV2', ['Bucket' => $bucket]) as $page) {
                foreach ($page['Contents'] ?? [] as $object) {
                    $client->deleteObject(['Bucket' => $bucket, 'Key' => $object['Key']]);
                }
            }
            $client->deleteBucket(['Bucket' => $bucket]);
        }
    }
}
