<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('candidate_validation_runs', function (Blueprint $table) {
            $table->char('identity', 64)->primary();
            $table->foreignUuid('normalized_artifact_id')->constrained('normalized_artifacts')->restrictOnDelete();
            $table->char('entity_sha256', 64);
            $table->char('findings_sha256', 64);
            $table->string('findings_disk', 64);
            $table->text('findings_object_key');
            $table->json('receipt');
            $table->timestampTz('created_at');
        });
        Schema::create('candidate_package_attempts', function (Blueprint $table) {
            $table->string('idempotency_key', 71)->primary();
            $table->uuid('package_id')->unique();
            $table->foreignUuid('source_release_id')->constrained('source_releases')->restrictOnDelete();
            $table->foreignUuid('ingestion_run_id')->constrained('ingestion_runs')->restrictOnDelete();
            $table->timestampTz('generated_at', 6);
        });
        Schema::table('candidate_packages', function (Blueprint $table) {
            $table->dropUnique(['archive_object_key']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('candidate_package_attempts');
        Schema::dropIfExists('candidate_validation_runs');
        // Do not restore archive uniqueness: distinct manifests may share archive bytes.
    }
};
