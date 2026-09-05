<?php

namespace Tests\Unit\Infrastructure\Candidate;

use App\Domain\Candidate\CandidateValidationRuleset;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Infrastructure\Candidate\JsonCandidateValidationRulesetLoader;
use Tests\TestCase;

final class JsonCandidateValidationRulesetLoaderTest extends TestCase
{
    public function test_refuses_a_changed_ruleset_pin(): void
    {
        $this->expectException(CandidateContractViolation::class);
        (new JsonCandidateValidationRulesetLoader(config('atlas.rulesets.candidate_validation.path'), str_repeat('f', 64)))->load();
    }

    public function test_integrity_gates_cannot_be_downgraded_by_policy(): void
    {
        $rules = json_decode(file_get_contents(config('atlas.rulesets.candidate_validation.path')), true);
        $rules['rules']['reference_invalid']['package_block'] = false;
        $this->expectException(CandidateContractViolation::class);
        $this->expectExceptionMessage('cannot disable integrity');
        new CandidateValidationRuleset($rules, str_repeat('a', 64));
    }
}
