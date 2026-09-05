<?php

namespace App\Application\Candidate;

use App\Application\Contracts\CandidateRecordMemberWriter;
use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CandidateRecordMember;
use App\Domain\Candidate\CanonicalCandidateEntity;

final readonly class BuildCandidateSourceDiffMember
{
    public function __construct(
        private CompareCandidateReleases $compare,
        private CandidateRecordMemberWriter $writer,
    ) {}

    /**
     * @param  iterable<CanonicalCandidateEntity>  $current
     * @param  iterable<CanonicalCandidateEntity>  $previous
     */
    public function handle(iterable $current, iterable $previous = []): CandidateArchiveMember
    {
        $diffs = $this->compare->handle($current, $previous);

        return $this->writer->write(
            CandidateRecordMember::SourceDiff,
            array_map(static fn ($diff): array => $diff->toRecord(), $diffs),
        );
    }
}
