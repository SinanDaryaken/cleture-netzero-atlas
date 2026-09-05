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
        Schema::create('candidate_packages', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignUuid('source_release_id')->constrained('source_releases')->restrictOnDelete();
            $table->foreignUuid('ingestion_run_id')->constrained('ingestion_runs')->restrictOnDelete();
            $table->uuid('previous_candidate_package_id')->nullable();
            $table->string('idempotency_key', 71)->unique();
            $table->string('schema_version', 32);
            $table->string('disk', 64);
            $table->text('archive_object_key')->unique();
            $table->char('archive_sha256', 64);
            $table->unsignedBigInteger('archive_size');
            $table->text('manifest_object_key')->unique();
            $table->char('manifest_sha256', 64);
            $table->unsignedBigInteger('manifest_size');
            $table->json('member_counts');
            $table->json('entity_counts');
            $table->json('source_diff_summary');
            $table->timestampTz('generated_at');
            $table->timestampTz('created_at');

            $table->index(['source_release_id', 'generated_at']);
            $table->index(['archive_sha256', 'archive_size']);
        });

        Schema::table('candidate_packages', function (Blueprint $table) {
            $table->foreign('previous_candidate_package_id')
                ->references('id')
                ->on('candidate_packages')
                ->restrictOnDelete();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('candidate_packages');
    }
};
