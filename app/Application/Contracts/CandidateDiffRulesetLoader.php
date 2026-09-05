<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidateDiffRuleset;

interface CandidateDiffRulesetLoader
{
    public function load(): CandidateDiffRuleset;
}
