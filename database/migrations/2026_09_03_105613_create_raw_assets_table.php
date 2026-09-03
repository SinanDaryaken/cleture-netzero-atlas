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
        Schema::create('raw_assets', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignUuid('source_release_id')->constrained('source_releases')->restrictOnDelete();
            $table->foreignUuid('ingestion_run_id')->constrained('ingestion_runs')->restrictOnDelete();
            $table->string('disk', 64);
            $table->text('object_key')->unique();
            $table->string('original_file_name');
            $table->text('source_url');
            $table->string('media_type')->nullable();
            $table->unsignedBigInteger('file_size');
            $table->char('sha256', 64);
            $table->string('upstream_checksum_algorithm', 16);
            $table->string('upstream_checksum', 128);
            $table->timestampTz('downloaded_at');
            $table->timestamps();

            $table->unique(['source_release_id', 'sha256']);
            $table->index(['sha256', 'file_size']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('raw_assets');
    }
};
