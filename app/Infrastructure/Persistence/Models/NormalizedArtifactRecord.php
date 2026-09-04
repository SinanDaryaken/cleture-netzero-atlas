<?php

namespace App\Infrastructure\Persistence\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class NormalizedArtifactRecord extends Model
{
    use HasUuids;

    protected $table = 'normalized_artifacts';

    protected $fillable = [
        'source_release_id',
        'ingestion_run_id',
        'parsed_artifact_id',
        'disk',
        'object_key',
        'format',
        'normalizer_version',
        'candidate_schema_version',
        'candidate_schema_sha256',
        'candidate_count',
        'finding_count',
        'file_size',
        'sha256',
        'metrics',
    ];

    protected function casts(): array
    {
        return [
            'candidate_count' => 'integer',
            'finding_count' => 'integer',
            'file_size' => 'integer',
            'metrics' => 'array',
        ];
    }
}
