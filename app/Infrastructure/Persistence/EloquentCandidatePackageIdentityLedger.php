<?php

namespace App\Infrastructure\Persistence;

use App\Application\Contracts\CandidatePackageIdentityLedger;
use App\Domain\Candidate\CandidatePackageContext;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use DateTimeImmutable;
use Illuminate\Support\Facades\DB;

final class EloquentCandidatePackageIdentityLedger implements CandidatePackageIdentityLedger
{
    public function reserve(string $idempotencyKey, CandidatePackageContext $context): CandidatePackageContext
    {
        return DB::transaction(function () use ($idempotencyKey, $context): CandidatePackageContext {
            // Serialize attempts for one release; uniqueness remains the durable backstop.
            DB::table('source_releases')->where('id', $context->sourceReleaseId)->lockForUpdate()->firstOrFail();
            $run = DB::table('ingestion_runs')->where('id', $context->producerRunId)->first();
            if ($run === null || $run->source_release_id !== $context->sourceReleaseId) {
                throw new CandidateContractViolation('Package producer run belongs to a different release.');
            }
            $existing = DB::table('candidate_package_attempts')->where('idempotency_key', $idempotencyKey)->first();
            if ($existing === null) {
                DB::table('candidate_package_attempts')->insert([
                    'idempotency_key' => $idempotencyKey, 'package_id' => $context->packageId,
                    'source_release_id' => $context->sourceReleaseId, 'ingestion_run_id' => $context->producerRunId,
                    'generated_at' => $context->generatedAt->format('Y-m-d H:i:s.uP'),
                ]);

                return $context;
            }
            if ($existing->source_release_id !== $context->sourceReleaseId) {
                throw new CandidateContractViolation('Package identity belongs to a different source release.');
            }

            return $context->withIdentity($existing->package_id, $existing->ingestion_run_id, new DateTimeImmutable($existing->generated_at));
        });
    }
}
