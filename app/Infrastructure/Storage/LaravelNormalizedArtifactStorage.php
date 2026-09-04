<?php

namespace App\Infrastructure\Storage;

use App\Application\Contracts\NormalizedArtifactStorage;
use App\Domain\Candidate\NormalizedCandidateDataset;
use App\Domain\Candidate\ParsedArtifactToNormalize;
use App\Domain\Candidate\StoredNormalizedArtifact;
use Illuminate\Filesystem\FilesystemManager;
use RuntimeException;

final readonly class LaravelNormalizedArtifactStorage implements NormalizedArtifactStorage
{
    public function __construct(
        private FilesystemManager $filesystems,
        private string $disk,
    ) {}

    public function store(
        ParsedArtifactToNormalize $input,
        NormalizedCandidateDataset $dataset,
    ): StoredNormalizedArtifact {
        $filesystem = $this->filesystems->disk($this->disk);
        $objectKey = $this->objectKey($input, $dataset);
        $alreadyExisted = $filesystem->exists($objectKey);

        if (! $alreadyExisted) {
            $stream = fopen($dataset->temporaryPath, 'rb');

            if ($stream === false) {
                throw new RuntimeException('Candidate draft artifact could not be opened for object storage.');
            }

            try {
                if (! $filesystem->put($objectKey, $stream)) {
                    throw new RuntimeException('Candidate draft artifact could not be written to object storage.');
                }
            } finally {
                fclose($stream);
            }
        }

        if ($filesystem->size($objectKey) !== $dataset->fileSize) {
            throw new RuntimeException('Stored candidate draft artifact size verification failed.');
        }

        return new StoredNormalizedArtifact(
            disk: $this->disk,
            objectKey: $objectKey,
            format: $dataset->format,
            normalizerVersion: $dataset->normalizerVersion,
            candidateSchemaVersion: $dataset->candidateSchemaVersion,
            candidateSchemaSha256: $dataset->candidateSchemaSha256,
            candidateCount: $dataset->candidateCount,
            findingCount: $dataset->findingCount,
            fileSize: $dataset->fileSize,
            sha256: $dataset->sha256,
            alreadyExisted: $alreadyExisted,
        );
    }

    private function objectKey(
        ParsedArtifactToNormalize $input,
        NormalizedCandidateDataset $dataset,
    ): string {
        $sourcePath = mb_strtolower($input->sourceCode);

        return "sources/{$sourcePath}/releases/{$input->releaseRevisionSha256}"
            ."/normalized/{$dataset->normalizerVersion}/{$dataset->sha256}.ndjson";
    }
}
