<?php

namespace Tests\Unit\Application\Candidate;

use App\Application\Candidate\BuildCandidateFindingMember;
use App\Domain\Candidate\NormalizationFinding;
use App\Infrastructure\Candidate\NdjsonCandidateRecordMemberWriter;
use App\Infrastructure\Candidate\Rfc8785CanonicalJson;
use App\Infrastructure\Contracts\OpisCandidateSchemaValidator;
use App\Infrastructure\Contracts\PinnedCandidateContractRegistry;
use Tests\TestCase;

final class BuildCandidateFindingMemberTest extends TestCase
{
    public function test_writes_schema_valid_findings_deterministically(): void
    {
        $builder = $this->builder();
        $finding = new NormalizationFinding(
            code: 'missing_unit',
            severity: 'blocking',
            candidateKey: 'source:dataset:factor:release:1',
            message: 'The source unit could not be resolved.',
            context: ['source_row' => 10],
        );

        $first = $builder->handle([$finding]);
        $second = $builder->handle([$finding]);

        try {
            $record = json_decode(trim(file_get_contents($first->temporaryPath)), true, flags: JSON_THROW_ON_ERROR);

            $this->assertSame('findings.ndjson', $first->path);
            $this->assertSame(1, $first->recordCount);
            $this->assertSame($first->sha256, $second->sha256);
            $this->assertSame(file_get_contents($first->temporaryPath), file_get_contents($second->temporaryPath));
            $this->assertSame('2.0.0', $record['schema_version']);
            $this->assertSame('missing_unit', $record['code']);
            $this->assertMatchesRegularExpression('/^finding:[a-f0-9]{64}$/', $record['finding_key']);
        } finally {
            unlink($first->temporaryPath);
            unlink($second->temporaryPath);
        }
    }

    public function test_writes_an_exact_empty_member_when_there_are_no_findings(): void
    {
        $member = $this->builder()->handle([]);

        try {
            $this->assertSame(0, $member->recordCount);
            $this->assertSame(0, $member->sizeBytes);
            $this->assertSame(hash('sha256', ''), $member->sha256);
        } finally {
            unlink($member->temporaryPath);
        }
    }

    private function builder(): BuildCandidateFindingMember
    {
        $contracts = new PinnedCandidateContractRegistry(
            base_path('resources/contracts/netzero-admin/candidate-v2/contract-manifest.json'),
        );
        $canonicalJson = new Rfc8785CanonicalJson;

        return new BuildCandidateFindingMember(
            contracts: $contracts,
            writer: new NdjsonCandidateRecordMemberWriter(
                $canonicalJson,
                new OpisCandidateSchemaValidator($contracts),
            ),
            canonicalJson: $canonicalJson,
        );
    }
}
