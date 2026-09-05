<?php

namespace Tests\Unit\Infrastructure\Contracts;

use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\CandidateContractDocument;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Infrastructure\Contracts\PinnedCandidateContractRegistry;
use Tests\TestCase;

final class PinnedCandidateContractRegistryTest extends TestCase
{
    public function test_loads_the_pinned_admin_contract_with_verified_provenance(): void
    {
        $registry = new PinnedCandidateContractRegistry(
            base_path('resources/contracts/netzero-admin/candidate-v1/contract-manifest.json'),
        );

        $document = $registry->get(CandidateContract::EntityRecord);

        $this->assertSame('1.0.0', $document->version);
        $this->assertSame('cleture-netzero-admin', $document->owner);
        $this->assertSame('f190d8cb02001fcb5ea1c8cf169dee611f195622', $document->upstreamCommit);
        $this->assertSame(hash('sha256', $document->contents), $document->sha256);
        $this->assertJson($document->contents);
    }

    public function test_loads_every_v2_contract_and_accepts_the_authoritative_archive_policy(): void
    {
        $registry = new PinnedCandidateContractRegistry(
            base_path('resources/contracts/netzero-admin/candidate-v2/contract-manifest.json'),
        );

        $documents = array_map($registry->get(...), CandidateContract::cases());
        $registry->assertPackageBuildReady();

        $this->assertCount(5, $documents);
        $this->assertSame(
            CandidateContract::cases(),
            array_map(
                static fn (CandidateContractDocument $document): CandidateContract => $document->contract,
                $documents,
            ),
        );
        $this->assertSame(['2.0.0'], array_values(array_unique(array_column($documents, 'version'))));
        $this->assertSame(
            ['37a30fae4f68cbea24a981d4e975463a856ac0ee'],
            array_values(array_unique(array_column($documents, 'upstreamCommit'))),
        );
    }

    public function test_rejects_a_v2_snapshot_when_the_pinned_upstream_manifest_bytes_change(): void
    {
        $directory = $this->temporaryContractDirectory();

        foreach (glob(base_path('resources/contracts/netzero-admin/candidate-v2/*')) ?: [] as $file) {
            copy($file, $directory.'/'.basename($file));
        }

        file_put_contents(
            $directory.'/atlas-candidate-contract-v2.manifest.json',
            "{}\n",
        );

        try {
            (new PinnedCandidateContractRegistry($directory.'/contract-manifest.json'))
                ->get(CandidateContract::EntityRecord);
            $this->fail('A modified upstream V2 manifest was accepted.');
        } catch (CandidateContractViolation $exception) {
            $this->assertSame(
                'Pinned candidate V2 upstream manifest failed integrity validation.',
                $exception->getMessage(),
            );
        } finally {
            $this->removeTemporaryDirectory($directory);
        }
    }

    public function test_fails_closed_when_a_pinned_schema_checksum_changes(): void
    {
        $directory = $this->temporaryContractDirectory();
        $schema = '{"$id":"urn:test:schema"}';
        file_put_contents($directory.'/schema.json', $schema);
        file_put_contents($directory.'/contract-manifest.json', json_encode([
            'snapshot_version' => '1.0.0',
            'owner' => 'cleture-netzero-admin',
            'upstream_repository' => 'cleture-netzero-admin',
            'upstream_commit' => str_repeat('a', 40),
            'contracts' => [[
                'name' => 'candidate_entity_record',
                'version' => '1.0.0',
                'path' => 'schema.json',
                'schema_id' => 'urn:test:schema',
                'sha256' => str_repeat('0', 64),
                'upstream_git_blob' => str_repeat('b', 40),
                'upstream_path' => 'schema.json',
            ]],
            'missing_package_record_contracts' => [],
        ], JSON_THROW_ON_ERROR));

        try {
            (new PinnedCandidateContractRegistry($directory.'/contract-manifest.json'))
                ->get(CandidateContract::EntityRecord);
            $this->fail('A modified pinned schema was accepted.');
        } catch (CandidateContractViolation $exception) {
            $this->assertSame(
                'Pinned candidate contract candidate_entity_record failed integrity validation.',
                $exception->getMessage(),
            );
        } finally {
            $this->removeTemporaryDirectory($directory);
        }
    }

    public function test_blocks_package_build_until_every_member_record_contract_is_pinned(): void
    {
        $registry = new PinnedCandidateContractRegistry(
            base_path('resources/contracts/netzero-admin/candidate-v1/contract-manifest.json'),
        );

        $this->expectException(CandidateContractViolation::class);
        $this->expectExceptionMessage(
            'Candidate package build is blocked by missing record contracts: '
            .'candidate_relationship_record, candidate_finding_record, candidate_source_diff_record.',
        );

        $registry->assertPackageBuildReady();
    }

    private function temporaryContractDirectory(): string
    {
        $directory = sys_get_temp_dir().'/atlas-contract-'.bin2hex(random_bytes(8));

        if (! mkdir($directory, 0700) && ! is_dir($directory)) {
            $this->fail('Temporary contract directory could not be created.');
        }

        return $directory;
    }

    private function removeTemporaryDirectory(string $directory): void
    {
        foreach (glob($directory.'/*') ?: [] as $file) {
            unlink($file);
        }

        rmdir($directory);
    }
}
