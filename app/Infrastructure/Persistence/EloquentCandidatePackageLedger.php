<?php

namespace App\Infrastructure\Persistence;

use App\Application\Contracts\CandidatePackageLedger;
use App\Domain\Candidate\CandidatePackageBuild;
use App\Domain\Candidate\CandidatePackageContext;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Candidate\RegisteredCandidatePackage;
use App\Domain\Candidate\StoredCandidatePackage;
use App\Infrastructure\Persistence\Models\CandidatePackageRecord;
use Illuminate\Support\Facades\DB;

final class EloquentCandidatePackageLedger implements CandidatePackageLedger
{
    public function register(
        CandidatePackageContext $context,
        CandidatePackageBuild $package,
        StoredCandidatePackage $storage,
    ): RegisteredCandidatePackage {
        return DB::transaction(function () use ($context, $package, $storage): RegisteredCandidatePackage {
            $manifest = $package->manifest;
            $idempotencyKey = $manifest['idempotency_key'] ?? null;

            if (! is_string($idempotencyKey)) {
                throw new CandidateContractViolation('Candidate package manifest has no idempotency key.');
            }

            $record = CandidatePackageRecord::query()->firstOrCreate(
                ['idempotency_key' => $idempotencyKey],
                [
                    'id' => $context->packageId,
                    'source_release_id' => $context->sourceReleaseId,
                    'ingestion_run_id' => $context->producerRunId,
                    'previous_candidate_package_id' => $context->previousPackageId,
                    'schema_version' => $manifest['schema_version'],
                    'disk' => $storage->disk,
                    'archive_object_key' => $storage->archiveObjectKey,
                    'archive_sha256' => $storage->archiveSha256,
                    'archive_size' => $storage->archiveSize,
                    'manifest_object_key' => $storage->manifestObjectKey,
                    'manifest_sha256' => $storage->manifestSha256,
                    'manifest_size' => $storage->manifestSize,
                    'member_counts' => [
                        'entities' => $manifest['counts']['entities'],
                        'relationships' => $manifest['counts']['relationships'],
                        'findings' => $manifest['counts']['findings'],
                        'source_diff' => $manifest['counts']['source_diff'],
                    ],
                    'entity_counts' => $manifest['counts']['by_entity_type'],
                    'source_diff_summary' => $manifest['source_diff_summary'],
                    'generated_at' => $context->generatedAt,
                ],
            );

            $this->assertSamePackage($record, $context, $storage);

            return new RegisteredCandidatePackage(
                packageId: $record->id,
                idempotencyKey: $record->idempotency_key,
                storage: $this->storage($record),
                alreadyExisted: ! $record->wasRecentlyCreated,
            );
        });
    }

    private function assertSamePackage(
        CandidatePackageRecord $record,
        CandidatePackageContext $context,
        StoredCandidatePackage $storage,
    ): void {
        if ($record->id !== $context->packageId
            || $record->source_release_id !== $context->sourceReleaseId
            || $record->ingestion_run_id !== $context->producerRunId
            || $record->previous_candidate_package_id !== $context->previousPackageId
            || $record->disk !== $storage->disk
            || $record->archive_object_key !== $storage->archiveObjectKey
            || $record->archive_sha256 !== $storage->archiveSha256
            || $record->archive_size !== $storage->archiveSize
            || $record->manifest_object_key !== $storage->manifestObjectKey
            || $record->manifest_sha256 !== $storage->manifestSha256
            || $record->manifest_size !== $storage->manifestSize
        ) {
            throw new CandidateContractViolation(
                'Candidate package idempotency key resolved to different immutable package facts.',
            );
        }
    }

    private function storage(CandidatePackageRecord $record): StoredCandidatePackage
    {
        return new StoredCandidatePackage(
            disk: $record->disk,
            archiveObjectKey: $record->archive_object_key,
            archiveSha256: $record->archive_sha256,
            archiveSize: $record->archive_size,
            manifestObjectKey: $record->manifest_object_key,
            manifestSha256: $record->manifest_sha256,
            manifestSize: $record->manifest_size,
            archiveAlreadyExisted: true,
            manifestAlreadyExisted: true,
        );
    }
}
