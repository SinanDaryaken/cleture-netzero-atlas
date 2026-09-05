<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CandidateRecordMember;

interface CandidateRecordMemberWriter
{
    /** @param iterable<array<string, mixed>> $records */
    public function write(CandidateRecordMember $member, iterable $records): CandidateArchiveMember;
}
