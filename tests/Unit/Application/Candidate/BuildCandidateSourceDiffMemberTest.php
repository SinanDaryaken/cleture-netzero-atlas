<?php

namespace Tests\Unit\Application\Candidate;

use App\Application\Candidate\BuildCandidateSourceDiffMember;
use App\Application\Candidate\CompareCandidateReleases;
use App\Domain\Candidate\CanonicalCandidateEntity;
use App\Infrastructure\Candidate\JsonCandidateDiffRulesetLoader;
use App\Infrastructure\Candidate\NdjsonCandidateRecordMemberWriter;
use App\Infrastructure\Candidate\Rfc8785CanonicalJson;
use App\Infrastructure\Contracts\OpisCandidateSchemaValidator;
use App\Infrastructure\Contracts\PinnedCandidateContractRegistry;
use Tests\TestCase;

final class BuildCandidateSourceDiffMemberTest extends TestCase
{
    public function test_writes_schema_valid_first_release_diff_records(): void
    {
        $contracts = new PinnedCandidateContractRegistry(
            base_path('resources/contracts/netzero-admin/candidate-v2/contract-manifest.json'),
        );
        $canonicalJson = new Rfc8785CanonicalJson;
        $comparator = new CompareCandidateReleases(
            contracts: $contracts,
            rulesets: new JsonCandidateDiffRulesetLoader(
                base_path('resources/rules/candidate/source-diff-v1.json'),
                'ec6976b14a1a761f5bc0b143db216ec13605e522b6bdab3d7f99646a9546b740',
            ),
            canonicalJson: $canonicalJson,
        );
        $builder = new BuildCandidateSourceDiffMember(
            $comparator,
            new NdjsonCandidateRecordMemberWriter(
                $canonicalJson,
                new OpisCandidateSchemaValidator($contracts),
            ),
        );

        $member = $builder->handle([$this->entity()]);

        try {
            $record = json_decode(trim(file_get_contents($member->temporaryPath)), true, flags: JSON_THROW_ON_ERROR);

            $this->assertSame('source-diff.ndjson', $member->path);
            $this->assertSame(1, $member->recordCount);
            $this->assertSame('added', $record['classification']);
            $this->assertSame('add', $record['changes'][0]['operation']);
            $this->assertSame('candidate-source-diff-v1', $record['diff_ruleset_version']);
        } finally {
            unlink($member->temporaryPath);
        }
    }

    private function entity(): CanonicalCandidateEntity
    {
        $recordSha256 = str_repeat('a', 64);
        $record = [
            'schema_version' => '2.0.0',
            'candidate_key' => 'source:dataset:factor:release:1',
            'logical_key' => 'source:dataset:factor',
            'variant_key' => 'source:dataset:factor:default',
            'record_sha256' => $recordSha256,
            'entity_type' => 'emission_factor',
            'primary_quantity' => ['value' => '1'],
            'provenance' => [['provenance_key' => 'source:dataset:factor:provenance']],
        ];

        return new CanonicalCandidateEntity(
            candidateKey: $record['candidate_key'],
            recordSha256: $recordSha256,
            record: $record,
            canonicalJson: (new Rfc8785CanonicalJson)->encode($record),
        );
    }
}
