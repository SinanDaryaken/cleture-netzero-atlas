<?php

namespace App\Infrastructure\Persistence;

use App\Application\Contracts\ParsingLedger;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use App\Domain\Ingestion\ParsedDataset;
use App\Domain\Ingestion\ParsingAttempt;
use App\Domain\Ingestion\RawAssetToParse;
use App\Domain\Ingestion\StoredParsedArtifact;
use App\Infrastructure\Persistence\Models\IngestionRunRecord;
use App\Infrastructure\Persistence\Models\ParsedArtifactRecord;
use App\Infrastructure\Persistence\Models\ParsedObservationRecord;
use App\Infrastructure\Persistence\Models\RawAssetRecord;
use App\Infrastructure\Persistence\Models\SourceRecord;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use JsonException;
use LogicException;
use Throwable;

final class EloquentParsingLedger implements ParsingLedger
{
    private const INSERT_CHUNK_SIZE = 200;

    public function beginParsing(string $sourceCode, string $parserVersion): ParsingAttempt
    {
        return DB::transaction(function () use ($sourceCode, $parserVersion): ParsingAttempt {
            $source = SourceRecord::query()
                ->where('code', $sourceCode)
                ->first();

            if ($source === null) {
                throw new SourceContractViolation(
                    "No acquired raw asset exists for source {$sourceCode}; run acquisition first.",
                );
            }

            $rawAsset = RawAssetRecord::query()
                ->with('sourceRelease')
                ->whereHas(
                    'sourceRelease',
                    fn ($query) => $query->where('source_id', $source->id),
                )
                ->orderByDesc('downloaded_at')
                ->orderByDesc('id')
                ->first();

            if ($rawAsset === null || $rawAsset->sourceRelease === null) {
                throw new SourceContractViolation(
                    "No acquired raw asset exists for source {$sourceCode}; run acquisition first.",
                );
            }

            $input = $this->rawAssetToParse($sourceCode, $rawAsset);
            $existing = ParsedArtifactRecord::query()
                ->where('raw_asset_id', $rawAsset->id)
                ->where('parser_version', $parserVersion)
                ->first();

            if ($existing !== null) {
                return new ParsingAttempt(
                    runId: $existing->ingestion_run_id,
                    releaseId: $existing->source_release_id,
                    rawAsset: $input,
                    existingParsedArtifact: $this->storedParsedArtifact($existing, true),
                );
            }

            $idempotencyKey = hash(
                'sha256',
                "{$sourceCode}|{$input->releaseRevisionSha256}|parse|{$parserVersion}",
            );
            $run = IngestionRunRecord::query()->firstOrCreate(
                ['idempotency_key' => $idempotencyKey],
                [
                    'source_id' => $source->id,
                    'source_release_id' => $rawAsset->source_release_id,
                    'phase' => 'parse_source',
                    'status' => 'running',
                    'started_at' => now(),
                ],
            );

            if ($run->status === 'failed') {
                $run->update([
                    'status' => 'running',
                    'started_at' => now(),
                    'completed_at' => null,
                    'failure_code' => null,
                    'failure_message' => null,
                    'metrics' => null,
                ]);
            } elseif ($run->status === 'completed') {
                throw new LogicException('Completed parsing run has no parsed artifact.');
            }

            return new ParsingAttempt(
                runId: $run->id,
                releaseId: $rawAsset->source_release_id,
                rawAsset: $input,
            );
        });
    }

    public function completeParsing(
        ParsingAttempt $attempt,
        ParsedDataset $dataset,
        StoredParsedArtifact $artifact,
    ): void {
        DB::transaction(function () use ($attempt, $dataset, $artifact): void {
            RawAssetRecord::query()
                ->whereKey($attempt->rawAsset->rawAssetId)
                ->lockForUpdate()
                ->firstOrFail();

            $existing = ParsedArtifactRecord::query()
                ->where('raw_asset_id', $attempt->rawAsset->rawAssetId)
                ->where('parser_version', $dataset->parserVersion)
                ->first();

            if ($existing !== null) {
                $this->assertDeterministicArtifact($existing, $artifact);
                $this->completeRun($attempt, $dataset);

                return;
            }

            $record = ParsedArtifactRecord::query()->create([
                'source_release_id' => $attempt->releaseId,
                'ingestion_run_id' => $attempt->runId,
                'raw_asset_id' => $attempt->rawAsset->rawAssetId,
                'disk' => $artifact->disk,
                'object_key' => $artifact->objectKey,
                'format' => $artifact->format,
                'parser_version' => $artifact->parserVersion,
                'schema_version' => $artifact->schemaVersion,
                'schema_sha256' => $artifact->schemaSha256,
                'source_encoding' => $artifact->sourceEncoding,
                'row_count' => $artifact->rowCount,
                'file_size' => $artifact->fileSize,
                'sha256' => $artifact->sha256,
            ]);

            $this->insertObservations($record->id, $dataset);
            $this->completeRun($attempt, $dataset);
        });
    }

    public function failParsing(ParsingAttempt $attempt, Throwable $exception): void
    {
        IngestionRunRecord::query()
            ->whereKey($attempt->runId)
            ->where('status', '!=', 'completed')
            ->update([
                'status' => 'failed',
                'completed_at' => now(),
                'failure_code' => class_basename($exception),
                'failure_message' => Str::limit($exception->getMessage(), 2000, ''),
            ]);
    }

    private function rawAssetToParse(string $sourceCode, RawAssetRecord $record): RawAssetToParse
    {
        $release = $record->sourceRelease;

        return new RawAssetToParse(
            sourceCode: $sourceCode,
            releaseVersion: $release->version,
            releaseRevisionSha256: $release->revision_sha256,
            reportedRowCount: $release->reported_row_count,
            rawAssetId: $record->id,
            disk: $record->disk,
            objectKey: $record->object_key,
            fileSize: $record->file_size,
            sha256: $record->sha256,
        );
    }

    private function storedParsedArtifact(
        ParsedArtifactRecord $record,
        bool $alreadyExisted,
    ): StoredParsedArtifact {
        return new StoredParsedArtifact(
            disk: $record->disk,
            objectKey: $record->object_key,
            format: $record->format,
            parserVersion: $record->parser_version,
            schemaVersion: $record->schema_version,
            schemaSha256: $record->schema_sha256,
            sourceEncoding: $record->source_encoding,
            rowCount: $record->row_count,
            fileSize: $record->file_size,
            sha256: $record->sha256,
            alreadyExisted: $alreadyExisted,
        );
    }

    private function assertDeterministicArtifact(
        ParsedArtifactRecord $existing,
        StoredParsedArtifact $artifact,
    ): void {
        if ($existing->sha256 !== $artifact->sha256
            || $existing->schema_sha256 !== $artifact->schemaSha256
            || $existing->row_count !== $artifact->rowCount
        ) {
            throw new SourceContractViolation(
                'The same raw asset and parser version produced a different parsed artifact.',
            );
        }
    }

    private function insertObservations(string $artifactId, ParsedDataset $dataset): void
    {
        $stream = fopen($dataset->temporaryPath, 'rb');

        if ($stream === false) {
            throw new LogicException('Parsed artifact could not be reopened for persistence.');
        }

        $batch = [];
        $inserted = 0;
        $createdAt = now();

        try {
            while (($line = fgets($stream)) !== false) {
                $observation = $this->decodeObservation($line);
                $batch[] = [
                    'id' => (string) Str::uuid(),
                    'parsed_artifact_id' => $artifactId,
                    'source_row' => $observation['source_row'],
                    'record_type' => $observation['record_type'],
                    'source_record_id' => $observation['source_record_id'],
                    'element_type' => $observation['element_type'],
                    'status' => $observation['status'],
                    'row_sha256' => $observation['row_sha256'],
                    'fields' => json_encode(
                        $observation['fields'],
                        JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
                    ),
                    'created_at' => $createdAt,
                ];

                if (count($batch) === self::INSERT_CHUNK_SIZE) {
                    DB::table((new ParsedObservationRecord)->getTable())->insert($batch);
                    $inserted += count($batch);
                    $batch = [];
                }
            }

            if ($batch !== []) {
                DB::table((new ParsedObservationRecord)->getTable())->insert($batch);
                $inserted += count($batch);
            }
        } finally {
            fclose($stream);
        }

        if ($inserted !== $dataset->rowCount) {
            throw new LogicException(
                "Parsed observation count mismatch: expected {$dataset->rowCount}, inserted {$inserted}.",
            );
        }
    }

    /**
     * @return array{
     *     source_row: int,
     *     record_type: string,
     *     source_record_id: string,
     *     element_type: string,
     *     status: string,
     *     row_sha256: string,
     *     fields: array<string, string>
     * }
     *
     * @throws JsonException
     */
    private function decodeObservation(string $line): array
    {
        $observation = json_decode($line, true, flags: JSON_THROW_ON_ERROR);

        if (! is_array($observation)
            || ! is_int($observation['source_row'] ?? null)
            || ! is_string($observation['record_type'] ?? null)
            || ! is_string($observation['source_record_id'] ?? null)
            || ! is_string($observation['element_type'] ?? null)
            || ! is_string($observation['status'] ?? null)
            || ! is_string($observation['row_sha256'] ?? null)
            || ! is_array($observation['fields'] ?? null)
        ) {
            throw new LogicException('Parsed artifact contains an invalid observation.');
        }

        return $observation;
    }

    private function completeRun(ParsingAttempt $attempt, ParsedDataset $dataset): void
    {
        IngestionRunRecord::query()
            ->whereKey($attempt->runId)
            ->update([
                'status' => 'completed',
                'completed_at' => now(),
                'metrics' => [
                    ...$dataset->metrics,
                    'parsed_bytes' => $dataset->fileSize,
                ],
            ]);
    }
}
