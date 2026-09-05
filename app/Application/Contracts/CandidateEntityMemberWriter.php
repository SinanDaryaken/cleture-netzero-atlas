<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CandidateEntityDraft;

interface CandidateEntityMemberWriter
{
    /** @param iterable<CandidateEntityDraft> $drafts */
    public function write(iterable $drafts): CandidateArchiveMember;
}
