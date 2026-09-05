<?php

namespace Tests\Unit\Application\Candidate;

use App\Application\Candidate\CompareCandidateReleases;
use App\Domain\Candidate\CanonicalCandidateEntity;
use App\Infrastructure\Candidate\JsonCandidateDiffRulesetLoader;
use App\Infrastructure\Candidate\Rfc8785CanonicalJson;
use App\Infrastructure\Contracts\PinnedCandidateContractRegistry;
use Tests\TestCase;

final class CompareCandidateReleasesTest extends TestCase
{
    public function test_classifies_added_changed_unchanged_and_removed_entities(): void
    {
        $diffs = $this->comparator()->handle(
            current: [
                $this->entity('changed:new', 'factor:changed', '2'),
                $this->entity('same:new', 'factor:same', '5'),
                $this->entity('added:new', 'factor:added', '8'),
            ],
            previous: [
                $this->entity('removed:old', 'factor:removed', '3'),
                $this->entity('same:old', 'factor:same', '5'),
                $this->entity('changed:old', 'factor:changed', '1'),
            ],
        );

        $byLogicalKey = [];

        foreach ($diffs as $diff) {
            $byLogicalKey[$diff->logicalKey] = $diff;
        }

        $this->assertSame('added', $byLogicalKey['factor:added']->classification);
        $this->assertSame('changed', $byLogicalKey['factor:changed']->classification);
        $this->assertSame('replace', $byLogicalKey['factor:changed']->changes[0]['operation']);
        $this->assertSame('/primary_quantity/value', $byLogicalKey['factor:changed']->changes[0]['json_pointer']);
        $this->assertSame('unchanged', $byLogicalKey['factor:same']->classification);
        $this->assertSame([], $byLogicalKey['factor:same']->changes);
        $this->assertSame('removed', $byLogicalKey['factor:removed']->classification);
    }

    public function test_produces_the_same_order_and_identity_for_the_same_inputs(): void
    {
        $comparator = $this->comparator();
        $first = $comparator->handle([
            $this->entity('b:new', 'factor:b', '2'),
            $this->entity('a:new', 'factor:a', '1'),
        ]);
        $second = $comparator->handle([
            $this->entity('a:new', 'factor:a', '1'),
            $this->entity('b:new', 'factor:b', '2'),
        ]);

        $this->assertSame(
            array_map(static fn ($diff): array => $diff->toRecord(), $first),
            array_map(static fn ($diff): array => $diff->toRecord(), $second),
        );
    }

    private function comparator(): CompareCandidateReleases
    {
        return new CompareCandidateReleases(
            contracts: new PinnedCandidateContractRegistry(
                base_path('resources/contracts/netzero-admin/candidate-v2/contract-manifest.json'),
            ),
            rulesets: new JsonCandidateDiffRulesetLoader(
                base_path('resources/rules/candidate/source-diff-v1.json'),
                'ec6976b14a1a761f5bc0b143db216ec13605e522b6bdab3d7f99646a9546b740',
            ),
            canonicalJson: new Rfc8785CanonicalJson,
        );
    }

    private function entity(string $candidateKey, string $logicalKey, string $value): CanonicalCandidateEntity
    {
        $recordSha256 = hash('sha256', $candidateKey.'|'.$value);
        $record = [
            'schema_version' => '2.0.0',
            'candidate_key' => $candidateKey,
            'logical_key' => $logicalKey,
            'variant_key' => $logicalKey.':default',
            'record_sha256' => $recordSha256,
            'entity_type' => 'emission_factor',
            'primary_quantity' => ['value' => $value],
            'provenance' => [['provenance_key' => $candidateKey.':provenance']],
        ];

        return new CanonicalCandidateEntity(
            candidateKey: $candidateKey,
            recordSha256: $recordSha256,
            record: $record,
            canonicalJson: (new Rfc8785CanonicalJson)->encode($record),
        );
    }
}
