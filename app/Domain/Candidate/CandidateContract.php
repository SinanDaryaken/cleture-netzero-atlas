<?php

namespace App\Domain\Candidate;

enum CandidateContract: string
{
    case PackageManifest = 'candidate_package_manifest';
    case EntityRecord = 'candidate_entity_record';
    case RelationshipRecord = 'candidate_relationship_record';
    case FindingRecord = 'candidate_finding_record';
    case SourceDiffRecord = 'candidate_source_diff_record';
}
