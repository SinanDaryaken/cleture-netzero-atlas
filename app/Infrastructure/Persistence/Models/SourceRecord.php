<?php

namespace App\Infrastructure\Persistence\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

final class SourceRecord extends Model
{
    use HasUuids;

    protected $table = 'sources';

    protected $fillable = [
        'code',
        'name',
        'publisher',
        'status',
        'metadata',
    ];

    protected function casts(): array
    {
        return [
            'metadata' => 'array',
        ];
    }
}
