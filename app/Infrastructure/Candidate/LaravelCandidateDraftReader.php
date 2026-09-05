<?php

namespace App\Infrastructure\Candidate;

use App\Application\Contracts\CandidateDraftReader;
use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Candidate\StoredNormalizedArtifact;
use Illuminate\Filesystem\FilesystemManager;
use InvalidArgumentException;
use JsonException;
use Throwable;

final readonly class LaravelCandidateDraftReader implements CandidateDraftReader
{
    private const MAX_LINE_BYTES = 10_000_000;

    public function __construct(private FilesystemManager $filesystems) {}

    public function read(StoredNormalizedArtifact $artifact): iterable
    {
        return (function () use ($artifact): \Generator {
            try {
                $stream = $this->filesystems->disk($artifact->disk)->readStream($artifact->objectKey);
            } catch (Throwable $exception) {
                throw new CandidateContractViolation('Normalized candidate draft artifact could not be read.', previous: $exception);
            }

            if (! is_resource($stream)) {
                throw new CandidateContractViolation('Normalized candidate draft artifact could not be opened.');
            }

            $hash = hash_init('sha256');
            $sizeBytes = 0;
            $recordCount = 0;

            try {
                while (($line = fgets($stream, self::MAX_LINE_BYTES + 1)) !== false) {
                    if (! str_ends_with($line, "\n") || strlen($line) > self::MAX_LINE_BYTES) {
                        throw new CandidateContractViolation('Normalized candidate draft line is incomplete or too large.');
                    }

                    hash_update($hash, $line);
                    $sizeBytes += strlen($line);
                    $recordCount++;

                    try {
                        $record = json_decode(rtrim($line, "\r\n"), true, 512, JSON_THROW_ON_ERROR);

                        if (! is_array($record) || array_is_list($record)) {
                            throw new CandidateContractViolation('Normalized candidate draft line must be a JSON object.');
                        }

                        yield CandidateEntityDraft::fromUnhashedRecord($record);
                    } catch (JsonException|InvalidArgumentException $exception) {
                        throw new CandidateContractViolation(
                            "Normalized candidate draft line {$recordCount} is invalid.",
                            previous: $exception,
                        );
                    }
                }
            } finally {
                fclose($stream);
            }

            if ($recordCount !== $artifact->candidateCount
                || $sizeBytes !== $artifact->fileSize
                || ! hash_equals($artifact->sha256, hash_final($hash))
            ) {
                throw new CandidateContractViolation('Normalized candidate draft artifact identity does not match persistence.');
            }
        })();
    }
}
