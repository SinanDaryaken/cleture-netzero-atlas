<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('normalization_findings', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignUuid('normalized_artifact_id')->constrained('normalized_artifacts')->cascadeOnDelete();
            $table->string('code', 128);
            $table->string('severity', 16);
            $table->text('candidate_key');
            $table->text('message');
            $table->json('context');
            $table->timestampTz('created_at');

            $table->index(['normalized_artifact_id', 'severity']);
            $table->index(['normalized_artifact_id', 'code']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('normalization_findings');
    }
};
