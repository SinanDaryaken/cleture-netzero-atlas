<?php

namespace App\Domain\Candidate;

use App\Domain\Candidate\Exceptions\CandidateContractViolation;

final readonly class CandidatePackageArtifact
{
    public const MEDIA_TYPE = 'application/vnd.netzeroatlas.candidate-package+zip';

    public function __construct(
        public string $temporaryPath,
        public string $objectKey,
        public string $sha256,
        public int $sizeBytes,
    ) {
        if (! is_file($this->temporaryPath)
            || preg_match('/^sha256\/[a-f0-9]{64}\.zip$/', $this->objectKey) !== 1
            || preg_match('/^[a-f0-9]{64}$/', $this->sha256) !== 1
            || $this->objectKey !== "sha256/{$this->sha256}.zip"
            || $this->sizeBytes < 1
            || filesize($this->temporaryPath) !== $this->sizeBytes
            || ! hash_equals($this->sha256, (string) hash_file('sha256', $this->temporaryPath))
        ) {
            throw new CandidateContractViolation('Candidate package artifact identity is invalid.');
        }
    }
}
