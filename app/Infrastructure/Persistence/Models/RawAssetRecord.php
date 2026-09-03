<?php

namespace App\Infrastructure\Persistence\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class RawAssetRecord extends Model
{
    use HasUuids;

    protected $table = 'raw_assets';

    protected $fillable = [
        'source_release_id',
        'ingestion_run_id',
        'disk',
        'object_key',
        'original_file_name',
        'source_url',
        'media_type',
        'file_size',
        'sha256',
        'upstream_checksum_algorithm',
        'upstream_checksum',
        'downloaded_at',
    ];

    protected function casts(): array
    {
        return [
            'file_size' => 'integer',
            'downloaded_at' => 'immutable_datetime',
        ];
    }
}
