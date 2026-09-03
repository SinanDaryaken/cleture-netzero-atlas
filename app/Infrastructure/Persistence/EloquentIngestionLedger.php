<?php

namespace App\Infrastructure\Persistence;

use App\Application\Contracts\IngestionLedger;
use App\Domain\Ingestion\AcquisitionAttempt;
use App\Domain\Ingestion\DownloadedAsset;
use App\Domain\Ingestion\SourceRelease;
use App\Domain\Ingestion\StoredRawAsset;
use App\Infrastructure\Persistence\Models\IngestionRunRecord;
use App\Infrastructure\Persistence\Models\RawAssetRecord;
use App\Infrastructure\Persistence\Models\SourceRecord;
use App\Infrastructure\Persistence\Models\SourceReleaseRecord;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Throwable;

final class EloquentIngestionLedger implements IngestionLedger
{
    public function beginAcquisition(SourceRelease $release): AcquisitionAttempt
    {
        return DB::transaction(function () use ($release): AcquisitionAttempt {
            $source = SourceRecord::query()->firstOrCreate(
                ['code' => $release->sourceCode],
                [
                    'name' => $release->metadata['source_name'] ?? $release->sourceCode,
                    'publisher' => $release->metadata['publisher'] ?? null,
                    'status' => 'active',
                    'metadata' => $release->metadata,
                ],
            );

            $releaseRecord = SourceReleaseRecord::query()->firstOrCreate(
                [
                    'source_id' => $source->id,
                    'revision_sha256' => $release->revisionSha256,
                ],
                [
                    'dataset_id' => $release->datasetId,
                    'version' => $release->version,
                    'reported_row_count' => $release->reportedRowCount,
                    'asset_url' => $release->assetUrl,
                    'file_name' => $release->fileName,
                    'file_size' => $release->fileSize,
                    'upstream_checksum_algorithm' => $release->upstreamChecksumAlgorithm,
                    'upstream_checksum' => $release->upstreamChecksum,
                    'license_title' => $release->licenseTitle,
                    'source_updated_at' => $release->sourceUpdatedAt,
                    'discovered_at' => now(),
                    'metadata' => $release->metadata,
                ],
            );

            $rawAsset = RawAssetRecord::query()
                ->where('source_release_id', $releaseRecord->id)
                ->first();

            if ($rawAsset !== null) {
                return new AcquisitionAttempt(
                    runId: $rawAsset->ingestion_run_id,
                    releaseId: $releaseRecord->id,
                    existingRawAsset: $this->storedRawAsset($rawAsset, true),
                );
            }

            $idempotencyKey = hash(
                'sha256',
                "{$release->sourceCode}|{$release->revisionSha256}|acquire_raw",
            );
            $run = IngestionRunRecord::query()->firstOrCreate(
                ['idempotency_key' => $idempotencyKey],
                [
                    'source_id' => $source->id,
                    'source_release_id' => $releaseRecord->id,
                    'phase' => 'acquire_raw',
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
                ]);
            }

            return new AcquisitionAttempt(
                runId: $run->id,
                releaseId: $releaseRecord->id,
            );
        });
    }

    public function completeAcquisition(
        AcquisitionAttempt $attempt,
        SourceRelease $release,
        DownloadedAsset $downloadedAsset,
        StoredRawAsset $storedRawAsset,
    ): void {
        DB::transaction(function () use (
            $attempt,
            $release,
            $downloadedAsset,
            $storedRawAsset,
        ): void {
            RawAssetRecord::query()->firstOrCreate(
                [
                    'source_release_id' => $attempt->releaseId,
                    'sha256' => $storedRawAsset->sha256,
                ],
                [
                    'ingestion_run_id' => $attempt->runId,
                    'disk' => $storedRawAsset->disk,
                    'object_key' => $storedRawAsset->objectKey,
                    'original_file_name' => $storedRawAsset->fileName,
                    'source_url' => $storedRawAsset->sourceUrl,
                    'media_type' => $storedRawAsset->mediaType,
                    'file_size' => $storedRawAsset->fileSize,
                    'upstream_checksum_algorithm' => $release->upstreamChecksumAlgorithm,
                    'upstream_checksum' => $release->upstreamChecksum,
                    'downloaded_at' => $downloadedAsset->downloadedAt,
                ],
            );

            IngestionRunRecord::query()
                ->whereKey($attempt->runId)
                ->update([
                    'status' => 'completed',
                    'completed_at' => now(),
                    'metrics' => [
                        'reported_rows' => $release->reportedRowCount,
                        'raw_bytes' => $storedRawAsset->fileSize,
                    ],
                ]);
        });
    }

    public function failAcquisition(AcquisitionAttempt $attempt, Throwable $exception): void
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

    private function storedRawAsset(RawAssetRecord $record, bool $alreadyExisted): StoredRawAsset
    {
        return new StoredRawAsset(
            disk: $record->disk,
            objectKey: $record->object_key,
            fileName: $record->original_file_name,
            sourceUrl: $record->source_url,
            mediaType: $record->media_type,
            fileSize: $record->file_size,
            sha256: $record->sha256,
            downloadedAt: $record->downloaded_at,
            alreadyExisted: $alreadyExisted,
        );
    }
}
