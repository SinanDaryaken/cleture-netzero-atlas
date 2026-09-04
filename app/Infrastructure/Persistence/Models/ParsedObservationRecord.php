<?php

namespace App\Infrastructure\Persistence\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class ParsedObservationRecord extends Model
{
    use HasUuids;

    public const UPDATED_AT = null;

    protected $table = 'parsed_observations';

    protected $fillable = [
        'parsed_artifact_id',
        'source_row',
        'record_type',
        'source_record_id',
        'element_type',
        'status',
        'row_sha256',
        'fields',
    ];

    protected function casts(): array
    {
        return [
            'source_row' => 'integer',
            'fields' => 'array',
        ];
    }
}
