<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\ParsedArtifactToNormalize;
use App\Domain\Ingestion\ParsedObservation;

interface ParsedObservationReader
{
    /** @return iterable<ParsedObservation> */
    public function read(ParsedArtifactToNormalize $input): iterable;
}
