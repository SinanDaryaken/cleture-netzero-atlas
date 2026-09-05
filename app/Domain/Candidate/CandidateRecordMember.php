<?php

namespace App\Domain\Candidate;

enum CandidateRecordMember: string
{
    case Findings = 'findings.ndjson';
    case SourceDiff = 'source-diff.ndjson';

    public function contract(): CandidateContract
    {
        return match ($this) {
            self::Findings => CandidateContract::FindingRecord,
            self::SourceDiff => CandidateContract::SourceDiffRecord,
        };
    }

    public function identityField(): string
    {
        return match ($this) {
            self::Findings => 'finding_key',
            self::SourceDiff => 'diff_key',
        };
    }
}
