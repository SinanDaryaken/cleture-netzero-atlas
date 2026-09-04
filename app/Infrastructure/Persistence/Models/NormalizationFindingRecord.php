<?php

namespace App\Infrastructure\Persistence\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class NormalizationFindingRecord extends Model
{
    use HasUuids;

    public const UPDATED_AT = null;

    protected $table = 'normalization_findings';

    protected $fillable = [
        'normalized_artifact_id',
        'code',
        'severity',
        'candidate_key',
        'message',
        'context',
    ];

    protected function casts(): array
    {
        return [
            'context' => 'array',
        ];
    }
}
