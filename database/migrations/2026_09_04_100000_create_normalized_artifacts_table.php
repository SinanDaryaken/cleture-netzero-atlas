<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('normalized_artifacts', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignUuid('source_release_id')->constrained('source_releases')->restrictOnDelete();
            $table->foreignUuid('ingestion_run_id')->constrained('ingestion_runs')->restrictOnDelete();
            $table->foreignUuid('parsed_artifact_id')->constrained('parsed_artifacts')->restrictOnDelete();
            $table->string('disk', 64);
            $table->text('object_key')->unique();
            $table->string('format', 32);
            $table->string('normalizer_version', 32);
            $table->string('candidate_schema_version', 32);
            $table->char('candidate_schema_sha256', 64);
            $table->unsignedBigInteger('candidate_count');
            $table->unsignedBigInteger('finding_count');
            $table->unsignedBigInteger('file_size');
            $table->char('sha256', 64);
            $table->json('metrics');
            $table->timestamps();

            $table->unique(
                ['parsed_artifact_id', 'normalizer_version', 'candidate_schema_sha256'],
                'normalized_artifacts_idempotency_unique',
            );
            $table->index(['sha256', 'file_size']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('normalized_artifacts');
    }
};
