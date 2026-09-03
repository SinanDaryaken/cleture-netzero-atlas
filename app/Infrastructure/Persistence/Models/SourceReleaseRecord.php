<?php

namespace App\Infrastructure\Persistence\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class SourceReleaseRecord extends Model
{
    use HasUuids;

    protected $table = 'source_releases';

    protected $fillable = [
        'source_id',
        'dataset_id',
        'version',
        'revision_sha256',
        'reported_row_count',
        'asset_url',
        'file_name',
        'file_size',
        'upstream_checksum_algorithm',
        'upstream_checksum',
        'license_title',
        'source_updated_at',
        'discovered_at',
        'metadata',
    ];

    protected function casts(): array
    {
        return [
            'reported_row_count' => 'integer',
            'file_size' => 'integer',
            'source_updated_at' => 'immutable_datetime',
            'discovered_at' => 'immutable_datetime',
            'metadata' => 'array',
        ];
    }
}
