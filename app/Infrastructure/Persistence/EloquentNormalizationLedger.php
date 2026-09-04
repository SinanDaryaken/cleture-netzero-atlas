<?php

namespace App\Infrastructure\Persistence;

use App\Application\Contracts\NormalizationLedger;
use App\Domain\Candidate\NormalizationAttempt;
use App\Domain\Candidate\NormalizedCandidateDataset;
use App\Domain\Candidate\ParsedArtifactToNormalize;
use App\Domain\Candidate\StoredNormalizedArtifact;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use App\Infrastructure\Persistence\Models\IngestionRunRecord;
use App\Infrastructure\Persistence\Models\NormalizationFindingRecord;
use App\Infrastructure\Persistence\Models\NormalizedArtifactRecord;
use App\Infrastructure\Persistence\Models\ParsedArtifactRecord;
use App\Infrastructure\Persistence\Models\SourceRecord;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use LogicException;
use Throwable;

final class EloquentNormalizationLedger implements NormalizationLedger
{
    private const INSERT_CHUNK_SIZE = 200;

    public function beginNormalization(
        string $sourceCode,
        string $normalizerVersion,
        string $candidateSchemaVersion,
        string $candidateSchemaSha256,
    ): NormalizationAttempt {
        return DB::transaction(function () use (
            $sourceCode,
            $normalizerVersion,
            $candidateSchemaVersion,
            $candidateSchemaSha256,
        ): NormalizationAttempt {
            $source = SourceRecord::query()->where('code', $sourceCode)->first();

            if ($source === null) {
                throw new SourceContractViolation(
                    "No parsed artifact exists for source {$sourceCode}; run parsing first.",
                );
            }

            $parsedArtifact = ParsedArtifactRecord::query()
                ->with(['sourceRelease', 'rawAsset'])
                ->whereHas('sourceRelease', fn ($query) => $query->where('source_id', $source->id))
                ->orderByDesc('created_at')
                ->orderByDesc('id')
                ->first();

            if ($parsedArtifact === null
                || $parsedArtifact->sourceRelease === null
                || $parsedArtifact->rawAsset === null
            ) {
                throw new SourceContractViolation(
                    "No parsed artifact exists for source {$sourceCode}; run parsing first.",
                );
            }

            $input = $this->input($sourceCode, $parsedArtifact);
            $existing = NormalizedArtifactRecord::query()
                ->where('parsed_artifact_id', $parsedArtifact->id)
                ->where('normalizer_version', $normalizerVersion)
                ->where('candidate_schema_sha256', $candidateSchemaSha256)
                ->first();

            if ($existing !== null) {
                return new NormalizationAttempt(
                    runId: $existing->ingestion_run_id,
                    releaseId: $existing->source_release_id,
                    input: $input,
                    existingArtifact: $this->storedArtifact($existing, true),
                );
            }

            $idempotencyKey = hash('sha256', implode('|', [
                $sourceCode,
                $input->parsedSha256,
                'normalize',
                $normalizerVersion,
                $candidateSchemaVersion,
                $candidateSchemaSha256,
            ]));
            $run = IngestionRunRecord::query()->firstOrCreate(
                ['idempotency_key' => $idempotencyKey],
                [
                    'source_id' => $source->id,
                    'source_release_id' => $parsedArtifact->source_release_id,
                    'phase' => 'normalize_source',
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
                throw new LogicException('Completed normalization run has no normalized artifact.');
            }

            return new NormalizationAttempt(
                runId: $run->id,
                releaseId: $parsedArtifact->source_release_id,
                input: $input,
            );
        });
    }

    public function completeNormalization(
        NormalizationAttempt $attempt,
        NormalizedCandidateDataset $dataset,
        StoredNormalizedArtifact $artifact,
    ): void {
        DB::transaction(function () use ($attempt, $dataset, $artifact): void {
            ParsedArtifactRecord::query()
                ->whereKey($attempt->input->parsedArtifactId)
                ->lockForUpdate()
                ->firstOrFail();

            $existing = NormalizedArtifactRecord::query()
                ->where('parsed_artifact_id', $attempt->input->parsedArtifactId)
                ->where('normalizer_version', $dataset->normalizerVersion)
                ->where('candidate_schema_sha256', $dataset->candidateSchemaSha256)
                ->first();

            if ($existing !== null) {
                $this->assertDeterministicArtifact($existing, $artifact);
                $this->completeRun($attempt, $dataset);

                return;
            }

            $record = NormalizedArtifactRecord::query()->create([
                'source_release_id' => $attempt->releaseId,
                'ingestion_run_id' => $attempt->runId,
                'parsed_artifact_id' => $attempt->input->parsedArtifactId,
                'disk' => $artifact->disk,
                'object_key' => $artifact->objectKey,
                'format' => $artifact->format,
                'normalizer_version' => $artifact->normalizerVersion,
                'candidate_schema_version' => $artifact->candidateSchemaVersion,
                'candidate_schema_sha256' => $artifact->candidateSchemaSha256,
                'candidate_count' => $artifact->candidateCount,
                'finding_count' => $artifact->findingCount,
                'file_size' => $artifact->fileSize,
                'sha256' => $artifact->sha256,
                'metrics' => $dataset->metrics,
            ]);

            $this->insertFindings($record->id, $dataset);
            $this->completeRun($attempt, $dataset);
        });
    }

    public function failNormalization(NormalizationAttempt $attempt, Throwable $exception): void
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

    private function input(string $sourceCode, ParsedArtifactRecord $record): ParsedArtifactToNormalize
    {
        $release = $record->sourceRelease;
        $rawAsset = $record->rawAsset;

        return new ParsedArtifactToNormalize(
            sourceCode: $sourceCode,
            datasetId: $release->dataset_id,
            releaseVersion: $release->version,
            releaseRevisionSha256: $release->revision_sha256,
            parsedArtifactId: $record->id,
            parsedDisk: $record->disk,
            parsedObjectKey: $record->object_key,
            parsedRowCount: $record->row_count,
            parsedSha256: $record->sha256,
            parserVersion: $record->parser_version,
            rawAssetKey: $rawAsset->object_key,
            rawAssetSha256: $rawAsset->sha256,
            retrievedAt: $rawAsset->downloaded_at->toDateTimeImmutable(),
            sourcePublishedAt: $release->source_updated_at?->toDateTimeImmutable(),
        );
    }

    private function storedArtifact(
        NormalizedArtifactRecord $record,
        bool $alreadyExisted,
    ): StoredNormalizedArtifact {
        return new StoredNormalizedArtifact(
            disk: $record->disk,
            objectKey: $record->object_key,
            format: $record->format,
            normalizerVersion: $record->normalizer_version,
            candidateSchemaVersion: $record->candidate_schema_version,
            candidateSchemaSha256: $record->candidate_schema_sha256,
            candidateCount: $record->candidate_count,
            findingCount: $record->finding_count,
            fileSize: $record->file_size,
            sha256: $record->sha256,
            alreadyExisted: $alreadyExisted,
        );
    }

    private function assertDeterministicArtifact(
        NormalizedArtifactRecord $existing,
        StoredNormalizedArtifact $artifact,
    ): void {
        if ($existing->sha256 !== $artifact->sha256
            || $existing->candidate_count !== $artifact->candidateCount
            || $existing->finding_count !== $artifact->findingCount
        ) {
            throw new SourceContractViolation(
                'The same parsed artifact and normalizer version produced a different candidate draft artifact.',
            );
        }
    }

    private function insertFindings(string $artifactId, NormalizedCandidateDataset $dataset): void
    {
        $batch = [];
        $inserted = 0;
        $createdAt = now();

        foreach ($dataset->findings as $finding) {
            $batch[] = [
                'id' => (string) Str::uuid(),
                'normalized_artifact_id' => $artifactId,
                'code' => $finding->code,
                'severity' => $finding->severity,
                'candidate_key' => $finding->candidateKey,
                'message' => $finding->message,
                'context' => json_encode(
                    $finding->context,
                    JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
                ),
                'created_at' => $createdAt,
            ];

            if (count($batch) === self::INSERT_CHUNK_SIZE) {
                DB::table((new NormalizationFindingRecord)->getTable())->insert($batch);
                $inserted += count($batch);
                $batch = [];
            }
        }

        if ($batch !== []) {
            DB::table((new NormalizationFindingRecord)->getTable())->insert($batch);
            $inserted += count($batch);
        }

        if ($inserted !== $dataset->findingCount) {
            throw new LogicException(
                "Normalization finding count mismatch: expected {$dataset->findingCount}, inserted {$inserted}.",
            );
        }
    }

    private function completeRun(NormalizationAttempt $attempt, NormalizedCandidateDataset $dataset): void
    {
        IngestionRunRecord::query()
            ->whereKey($attempt->runId)
            ->update([
                'status' => 'completed',
                'completed_at' => now(),
                'metrics' => [
                    ...$dataset->metrics,
                    'candidate_draft_bytes' => $dataset->fileSize,
                    'normalization_findings' => $dataset->findingCount,
                ],
            ]);
    }
}
