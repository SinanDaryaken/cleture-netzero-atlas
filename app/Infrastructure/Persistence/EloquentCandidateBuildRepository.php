<?php

namespace App\Infrastructure\Persistence;

use App\Application\Contracts\CandidateBuildRepository;
use App\Application\Contracts\CanonicalJson;
use App\Domain\Candidate\CandidateBuildInput;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Candidate\NormalizationFinding;
use App\Domain\Candidate\StoredNormalizedArtifact;
use App\Domain\Candidate\ValidatedCandidateDataset;
use App\Infrastructure\Persistence\Models\IngestionRunRecord;
use App\Infrastructure\Persistence\Models\NormalizationFindingRecord;
use App\Infrastructure\Persistence\Models\NormalizedArtifactRecord;
use App\Infrastructure\Persistence\Models\ParsedArtifactRecord;
use App\Infrastructure\Persistence\Models\SourceRecord;
use Illuminate\Filesystem\FilesystemManager;
use Illuminate\Support\Facades\DB;

final readonly class EloquentCandidateBuildRepository implements CandidateBuildRepository
{
    public function __construct(private CanonicalJson $json, private FilesystemManager $filesystems, private string $disk) {}

    public function input(string $normalizedArtifactId): CandidateBuildInput
    {
        $artifact = NormalizedArtifactRecord::query()->findOrFail($normalizedArtifactId);
        $parsed = ParsedArtifactRecord::query()->with(['sourceRelease', 'rawAsset'])->findOrFail($artifact->parsed_artifact_id);
        $release = $parsed->sourceRelease;
        $raw = $parsed->rawAsset;
        $source = SourceRecord::query()->findOrFail($release->source_id);
        if ($artifact->source_release_id !== $release->id || $raw->source_release_id !== $release->id) {
            throw new CandidateContractViolation('Normalized artifact lineage has inconsistent releases.');
        }
        $assets = [[
            'asset_key' => $raw->object_key, 'sha256' => $raw->sha256, 'size_bytes' => $raw->file_size,
            'media_type' => $raw->media_type, 'source_uri' => $raw->source_url, 'retrieved_at' => $raw->downloaded_at->toISOString(),
        ]];

        return new CandidateBuildInput($artifact->id, $source->id, $release->id,
            ['code' => $source->code, 'dataset_id' => $release->dataset_id],
            ['version' => $release->version, 'revision_sha256' => $release->revision_sha256, 'source_published_at' => $release->source_updated_at?->toISOString()],
            ['set_sha256' => hash('sha256', $this->json->encode($assets)), 'asset_count' => count($assets), 'assets' => $assets],
            ['parser_version' => $parsed->parser_version, 'candidate_schema_version' => $artifact->candidate_schema_version,
                'parser_schema_fingerprint_sha256' => $parsed->schema_sha256, 'normalizer_version' => $artifact->normalizer_version,
                'canonicalization_version' => 'rfc8785-decimal-string-v1'],
            new StoredNormalizedArtifact($artifact->disk, $artifact->object_key, $artifact->format, $artifact->normalizer_version,
                $artifact->candidate_schema_version, $artifact->candidate_schema_sha256, $artifact->candidate_count,
                $artifact->finding_count, $artifact->file_size, $artifact->sha256, true), $release->license_title);
    }

    public function normalizationFindings(string $normalizedArtifactId): iterable
    {
        foreach (NormalizationFindingRecord::query()->where('normalized_artifact_id', $normalizedArtifactId)
            ->orderBy('candidate_key')->orderBy('code')->orderBy('id')->lazy() as $finding) {
            yield new NormalizationFinding($finding->code, $finding->severity, $finding->candidate_key, $finding->message, $finding->context);
        }
    }

    public function recordValidation(string $normalizedArtifactId, ValidatedCandidateDataset $dataset): void
    {
        $member = $dataset->findings;
        $path = 'validation/findings/sha256/'.$member->sha256.'.ndjson';
        $filesystem = $this->filesystems->disk($this->disk);
        if (! $filesystem->exists($path)) {
            $stream = fopen($member->temporaryPath, 'rb');
            try {
                if (! $filesystem->put($path, $stream)) {
                    throw new CandidateContractViolation('Validation findings could not be persisted.');
                }
            } finally {
                fclose($stream);
            }
        }
        $stream = $filesystem->readStream($path);
        if (! is_resource($stream)) {
            throw new CandidateContractViolation('Stored findings could not be verified.');
        }
        try {
            $hash = hash_init('sha256');
            $size = hash_update_stream($hash, $stream);
            if ($size !== $member->sizeBytes || ! hash_equals($member->sha256, hash_final($hash))) {
                throw new CandidateContractViolation('Stored findings identity mismatch.');
            }
        } finally {
            fclose($stream);
        }
        $receipt = $this->json->encode(get_object_vars($dataset->receipt));
        DB::transaction(function () use ($normalizedArtifactId, $dataset, $path, $receipt): void {
            DB::table('normalized_artifacts')->where('id', $normalizedArtifactId)->lockForUpdate()->firstOrFail();
            $existing = DB::table('candidate_validation_runs')->where('identity', $dataset->receipt->identity)->first();
            if ($existing !== null) {
                if ($existing->normalized_artifact_id !== $normalizedArtifactId || $this->json->encode(json_decode($existing->receipt)) !== $receipt) {
                    throw new CandidateContractViolation('Validation identity resolved to different evidence.');
                }

                return;
            }
            DB::table('candidate_validation_runs')->insert([
                'identity' => $dataset->receipt->identity, 'normalized_artifact_id' => $normalizedArtifactId,
                'entity_sha256' => $dataset->receipt->entitySha256, 'findings_sha256' => $dataset->receipt->findingSha256,
                'findings_disk' => $this->disk, 'findings_object_key' => $path, 'receipt' => $receipt, 'created_at' => now(),
            ]);
        });
    }

    public function begin(CandidateBuildInput $input, string $identity): string
    {
        return IngestionRunRecord::query()->firstOrCreate(['idempotency_key' => $identity], [
            'source_id' => $input->sourceId, 'source_release_id' => $input->sourceReleaseId,
            'phase' => 'build_candidate', 'status' => 'running', 'started_at' => now(),
        ])->id;
    }

    public function finish(string $runId, string $status, array $metrics): void
    {
        IngestionRunRecord::query()->whereKey($runId)->where('status', '!=', 'completed')->update([
            'status' => $status, 'completed_at' => now(), 'metrics' => $metrics,
        ]);
    }
}
