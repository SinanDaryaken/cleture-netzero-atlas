<?php

namespace App\Infrastructure\Persistence\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class IngestionRunRecord extends Model
{
    use HasUuids;

    protected $table = 'ingestion_runs';

    protected $fillable = [
        'source_id',
        'source_release_id',
        'idempotency_key',
        'phase',
        'status',
        'started_at',
        'completed_at',
        'failure_code',
        'failure_message',
        'metrics',
    ];

    protected function casts(): array
    {
        return [
            'started_at' => 'immutable_datetime',
            'completed_at' => 'immutable_datetime',
            'metrics' => 'array',
        ];
    }
}
