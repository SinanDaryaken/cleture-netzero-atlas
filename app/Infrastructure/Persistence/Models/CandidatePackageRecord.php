<?php

namespace App\Infrastructure\Persistence\Models;

use Illuminate\Database\Eloquent\Model;

final class CandidatePackageRecord extends Model
{
    public const UPDATED_AT = null;

    protected $table = 'candidate_packages';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $fillable = [
        'id',
        'source_release_id',
        'ingestion_run_id',
        'previous_candidate_package_id',
        'idempotency_key',
        'schema_version',
        'disk',
        'archive_object_key',
        'archive_sha256',
        'archive_size',
        'manifest_object_key',
        'manifest_sha256',
        'manifest_size',
        'member_counts',
        'entity_counts',
        'source_diff_summary',
        'generated_at',
    ];

    protected function casts(): array
    {
        return [
            'archive_size' => 'integer',
            'manifest_size' => 'integer',
            'member_counts' => 'array',
            'entity_counts' => 'array',
            'source_diff_summary' => 'array',
            'generated_at' => 'immutable_datetime',
        ];
    }
}
