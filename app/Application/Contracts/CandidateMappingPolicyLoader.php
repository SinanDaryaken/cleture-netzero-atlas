<?php

namespace App\Application\Contracts;

interface CandidateMappingPolicyLoader
{
    public function identity(): array;
}
