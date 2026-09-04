<?php

namespace App\Domain\Candidate;

enum CandidateContract: string
{
    case PackageManifest = 'candidate_package_manifest';
    case EntityRecord = 'candidate_entity_record';
}
