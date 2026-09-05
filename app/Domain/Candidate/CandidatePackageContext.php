<?php

namespace App\Domain\Candidate;

use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use DateTimeImmutable;

final readonly class CandidatePackageContext
{
    /**
     * @param  array<string, mixed>  $source
     * @param  array<string, mixed>  $release
     * @param  array<string, mixed>  $rawAssets
     * @param  array<string, mixed>  $pipeline
     * @param  array<string, mixed>  $catalogSnapshots
     * @param  array<string, mixed>  $license
     * @param  array<string, int>  $entityCounts
     * @param  array{added: int, changed: int, unchanged: int, removed: int}  $sourceDiffSummary
     * @param  array<string, mixed>  $extensions
     */
    public function __construct(
        public string $packageId,
        public string $sourceReleaseId,
        public array $source,
        public array $release,
        public array $rawAssets,
        public array $pipeline,
        public array $catalogSnapshots,
        public array $license,
        public array $entityCounts,
        public ?string $previousPackageId,
        public array $sourceDiffSummary,
        public DateTimeImmutable $generatedAt,
        public string $producerRunId,
        public string $storageProfile,
        public array $extensions = [],
    ) {
        if ($this->packageId === ''
            || $this->sourceReleaseId === ''
            || $this->producerRunId === ''
            || $this->storageProfile === ''
        ) {
            throw new CandidateContractViolation('Candidate package context identity cannot be empty.');
        }

        if ($this->entityCounts === [] || array_sum($this->entityCounts) < 1) {
            throw new CandidateContractViolation('Candidate package entity counts cannot be empty.');
        }

        foreach ($this->entityCounts as $entityType => $count) {
            if (! is_string($entityType) || $entityType === '' || ! is_int($count) || $count < 0) {
                throw new CandidateContractViolation('Candidate package entity counts are invalid.');
            }
        }

        $summaryKeys = array_keys($this->sourceDiffSummary);
        sort($summaryKeys, SORT_STRING);

        if ($summaryKeys !== ['added', 'changed', 'removed', 'unchanged']) {
            throw new CandidateContractViolation('Candidate package source diff summary shape is invalid.');
        }

        foreach ($this->sourceDiffSummary as $count) {
            if (! is_int($count) || $count < 0) {
                throw new CandidateContractViolation('Candidate package source diff summary is invalid.');
            }
        }
    }
}
