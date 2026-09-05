<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidateValidationRuleset;

interface CandidateValidationRulesetLoader
{
    public function load(): CandidateValidationRuleset;
}
