<?php

namespace App\Application\Contracts;

interface CandidateReleaseComparison
{
    public function compare(iterable $current, iterable $previous): iterable;
}
