<?php

namespace Tests\Feature\Console\Commands;

use App\Application\Candidate\PrepareCandidatePackage;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use Illuminate\Foundation\Testing\LazilyRefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use Tests\Support\CandidateFixture;
use Tests\Support\CandidatePipelineFixture;
use Tests\TestCase;

final class BuildCandidatePackageCommandTest extends TestCase
{
    use LazilyRefreshDatabase;

    public function test_builds_a_review_package_and_reuses_the_same_identity_on_retry(): void
    {
        Storage::fake('atlas_processing');
        Storage::fake('atlas_catalogs');
        Storage::fake('atlas_candidates');
        $plan = CandidatePipelineFixture::seed();
        $path = tempnam(sys_get_temp_dir(), 'atlas-plan-test-');
        file_put_contents($path, json_encode($plan, JSON_THROW_ON_ERROR));

        try {
            $this->artisan('atlas:candidate:build', ['plan' => $path])->assertSuccessful();
            $first = DB::table('candidate_packages')->first();
            $this->artisan('atlas:candidate:build', ['plan' => $path])->assertSuccessful();
            $this->assertDatabaseCount('candidate_packages', 1);
            $this->assertDatabaseCount('candidate_package_attempts', 1);
            $this->assertDatabaseCount('candidate_validation_runs', 1);
            $this->assertSame($first->id, DB::table('candidate_packages')->value('id'));
            Storage::disk('atlas_candidates')->assertExists($first->archive_object_key);
            $receipt = json_decode(DB::table('candidate_validation_runs')->value('receipt'), true, 512, JSON_THROW_ON_ERROR);
            $this->assertFalse($receipt['packageBlocked']);
            $this->assertSame(1, $receipt['summary']['blocking']);
        } finally {
            unlink($path);
        }
    }

    public function test_retains_integrity_findings_without_creating_a_package(): void
    {
        Storage::fake('atlas_processing');
        Storage::fake('atlas_catalogs');
        Storage::fake('atlas_candidates');
        $draft = CandidateFixture::draft()->toUnhashedRecord();
        $draft['components'][0]['methodology_ref'] = 'missing';
        $plan = CandidatePipelineFixture::seed($draft);

        $result = app(PrepareCandidatePackage::class)->handle($plan, 'atlas_candidates');

        $this->assertNull($result->package);
        $this->assertTrue($result->validation->packageBlocked);
        $this->assertDatabaseCount('candidate_packages', 0);
        $this->assertDatabaseCount('candidate_validation_runs', 1);
        $this->assertSame([], Storage::disk('atlas_candidates')->allFiles());
    }

    public function test_missing_license_terms_prevent_package_and_validation_records(): void
    {
        Storage::fake('atlas_processing');
        Storage::fake('atlas_catalogs');
        Storage::fake('atlas_candidates');
        $plan = CandidatePipelineFixture::seed();
        $descriptor = json_decode(Storage::disk('atlas_processing')->get($plan['license_descriptor_path']), true);
        Storage::disk('atlas_processing')->put($descriptor['terms_object_key'], 'tampered');

        try {
            app(PrepareCandidatePackage::class)->handle($plan, 'atlas_candidates');
            $this->fail('Tampered license terms were accepted.');
        } catch (CandidateContractViolation $exception) {
            $this->assertStringContainsString('License terms exact bytes', $exception->getMessage());
        }
        $this->assertDatabaseCount('candidate_packages', 0);
        $this->assertDatabaseCount('candidate_validation_runs', 0);
    }

    public function test_reads_a_verified_previous_package_and_produces_unchanged_diff(): void
    {
        Storage::fake('atlas_processing');
        Storage::fake('atlas_catalogs');
        Storage::fake('atlas_candidates');
        $plan = CandidatePipelineFixture::seed();
        $prepare = app(PrepareCandidatePackage::class);
        $first = $prepare->handle($plan, 'atlas_candidates');
        $plan['previous_package_id'] = $first->package->packageId;

        $second = $prepare->handle($plan, 'atlas_candidates');

        $manifest = json_decode(Storage::disk('atlas_candidates')->get($second->package->storage->manifestObjectKey), true);
        $this->assertSame(['added' => 0, 'changed' => 0, 'removed' => 0, 'unchanged' => 1], $manifest['source_diff_summary']);
        $this->assertSame($first->package->packageId, $manifest['previous_package_id']);
        $this->assertDatabaseCount('candidate_packages', 2);
    }

    public function test_new_license_evidence_can_share_archive_bytes_without_reusing_manifest_identity(): void
    {
        Storage::fake('atlas_processing');
        Storage::fake('atlas_catalogs');
        Storage::fake('atlas_candidates');
        $plan = CandidatePipelineFixture::seed();
        $prepare = app(PrepareCandidatePackage::class);
        $first = $prepare->handle($plan, 'atlas_candidates');
        $descriptor = json_decode(Storage::disk('atlas_processing')->get($plan['license_descriptor_path']), true);
        $descriptor['license']['attribution'] = 'Updated test attribution';
        $bytes = json_encode($descriptor, JSON_THROW_ON_ERROR);
        $plan['license_descriptor_sha256'] = hash('sha256', $bytes);
        $plan['license_descriptor_path'] = 'licenses/sha256/'.$plan['license_descriptor_sha256'].'.json';
        Storage::disk('atlas_processing')->put($plan['license_descriptor_path'], $bytes);

        $second = $prepare->handle($plan, 'atlas_candidates');

        $this->assertNotSame($first->package->packageId, $second->package->packageId);
        $this->assertSame($first->package->storage->archiveObjectKey, $second->package->storage->archiveObjectKey);
        $this->assertNotSame($first->package->storage->manifestObjectKey, $second->package->storage->manifestObjectKey);
        $this->assertDatabaseCount('candidate_packages', 2);
        $this->assertDatabaseCount('candidate_validation_runs', 2);
    }
}
