<?php

namespace App\Infrastructure\Persistence\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class ParsedArtifactRecord extends Model
{
    use HasUuids;

    protected $table = 'parsed_artifacts';

    protected $fillable = [
        'source_release_id',
        'ingestion_run_id',
        'raw_asset_id',
        'disk',
        'object_key',
        'format',
        'parser_version',
        'schema_version',
        'schema_sha256',
        'source_encoding',
        'row_count',
        'file_size',
        'sha256',
    ];

    protected function casts(): array
    {
        return [
            'row_count' => 'integer',
            'file_size' => 'integer',
        ];
    }
}
