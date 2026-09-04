<?php

namespace App\Infrastructure\Storage;

use App\Application\Contracts\ParsedObservationReader;
use App\Domain\Candidate\ParsedArtifactToNormalize;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use App\Domain\Ingestion\ParsedObservation;
use Generator;
use Illuminate\Filesystem\FilesystemManager;
use JsonException;
use RuntimeException;

final readonly class LaravelParsedObservationReader implements ParsedObservationReader
{
    public function __construct(private FilesystemManager $filesystems) {}

    public function read(ParsedArtifactToNormalize $input): iterable
    {
        return $this->observations($input);
    }

    /** @return Generator<int, ParsedObservation> */
    private function observations(ParsedArtifactToNormalize $input): Generator
    {
        $stream = $this->filesystems->disk($input->parsedDisk)->readStream($input->parsedObjectKey);

        if (! is_resource($stream)) {
            throw new RuntimeException('Parsed artifact could not be opened for normalization.');
        }

        $hash = hash_init('sha256');
        $rowCount = 0;

        try {
            while (($line = fgets($stream)) !== false) {
                hash_update($hash, $line);
                $rowCount++;
                yield $this->decode($line);
            }

            if ($rowCount !== $input->parsedRowCount) {
                throw new SourceContractViolation(
                    "Parsed artifact row count changed: expected {$input->parsedRowCount}, read {$rowCount}.",
                );
            }

            $sha256 = hash_final($hash);

            if (! hash_equals($input->parsedSha256, $sha256)) {
                throw new SourceContractViolation('Parsed artifact checksum changed before normalization.');
            }
        } finally {
            fclose($stream);
        }
    }

    private function decode(string $line): ParsedObservation
    {
        try {
            $observation = json_decode($line, true, flags: JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new SourceContractViolation('Parsed artifact contains invalid JSON.', previous: $exception);
        }

        if (! is_array($observation)
            || ! is_int($observation['source_row'] ?? null)
            || ! is_string($observation['record_type'] ?? null)
            || ! is_string($observation['source_record_id'] ?? null)
            || ! is_string($observation['element_type'] ?? null)
            || ! is_string($observation['status'] ?? null)
            || ! is_string($observation['row_sha256'] ?? null)
            || ! is_array($observation['fields'] ?? null)
        ) {
            throw new SourceContractViolation('Parsed artifact contains an invalid observation contract.');
        }

        try {
            return new ParsedObservation(
                sourceRow: $observation['source_row'],
                recordType: $observation['record_type'],
                sourceRecordId: $observation['source_record_id'],
                elementType: $observation['element_type'],
                status: $observation['status'],
                rowSha256: $observation['row_sha256'],
                fields: $observation['fields'],
            );
        } catch (\InvalidArgumentException $exception) {
            throw new SourceContractViolation('Parsed artifact observation integrity is invalid.', previous: $exception);
        }
    }
}
