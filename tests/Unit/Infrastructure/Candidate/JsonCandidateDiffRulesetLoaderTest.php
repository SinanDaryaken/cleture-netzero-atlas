<?php

namespace Tests\Unit\Infrastructure\Candidate;

use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Infrastructure\Candidate\JsonCandidateDiffRulesetLoader;
use Tests\TestCase;

final class JsonCandidateDiffRulesetLoaderTest extends TestCase
{
    public function test_loads_the_pinned_ruleset_and_resolves_domains_by_prefix(): void
    {
        $ruleset = $this->loader()->load();

        $this->assertSame('candidate-source-diff-v1', $ruleset->rulesetVersion);
        $this->assertSame('value', $ruleset->domainFor('/primary_quantity/value'));
        $this->assertSame('geography', $ruleset->domainFor('/geography_proposals/0/raw_label'));
        $this->assertTrue($ruleset->excludes('/record_sha256'));
        $this->assertTrue($ruleset->excludes('/provenance/0/source_asset_sha256'));
    }

    public function test_rejects_ruleset_bytes_that_do_not_match_the_pin(): void
    {
        $this->expectException(CandidateContractViolation::class);
        $this->expectExceptionMessage('checksum does not match');

        new JsonCandidateDiffRulesetLoader(
            path: base_path('resources/rules/candidate/source-diff-v1.json'),
            expectedSha256: str_repeat('0', 64),
        )->load();
    }

    private function loader(): JsonCandidateDiffRulesetLoader
    {
        return new JsonCandidateDiffRulesetLoader(
            path: base_path('resources/rules/candidate/source-diff-v1.json'),
            expectedSha256: 'ec6976b14a1a761f5bc0b143db216ec13605e522b6bdab3d7f99646a9546b740',
        );
    }
}
