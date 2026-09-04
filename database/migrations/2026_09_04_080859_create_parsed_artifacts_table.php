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
        Schema::create('parsed_artifacts', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignUuid('source_release_id')->constrained('source_releases')->restrictOnDelete();
            $table->foreignUuid('ingestion_run_id')->constrained('ingestion_runs')->restrictOnDelete();
            $table->foreignUuid('raw_asset_id')->constrained('raw_assets')->restrictOnDelete();
            $table->string('disk', 64);
            $table->text('object_key')->unique();
            $table->string('format', 32);
            $table->string('parser_version', 32);
            $table->string('schema_version', 128);
            $table->char('schema_sha256', 64);
            $table->string('source_encoding', 32);
            $table->unsignedBigInteger('row_count');
            $table->unsignedBigInteger('file_size');
            $table->char('sha256', 64);
            $table->timestamps();

            $table->unique(['raw_asset_id', 'parser_version']);
            $table->index(['sha256', 'file_size']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('parsed_artifacts');
    }
};
