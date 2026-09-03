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
        Schema::create('source_releases', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignUuid('source_id')->constrained('sources')->restrictOnDelete();
            $table->string('dataset_id');
            $table->string('version', 64);
            $table->char('revision_sha256', 64);
            $table->unsignedBigInteger('reported_row_count');
            $table->text('asset_url');
            $table->string('file_name');
            $table->unsignedBigInteger('file_size');
            $table->string('upstream_checksum_algorithm', 16);
            $table->string('upstream_checksum', 128);
            $table->string('license_title');
            $table->timestampTz('source_updated_at')->nullable();
            $table->timestampTz('discovered_at');
            $table->json('metadata')->nullable();
            $table->timestamps();

            $table->unique(['source_id', 'revision_sha256']);
            $table->index(['source_id', 'dataset_id', 'version']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('source_releases');
    }
};
