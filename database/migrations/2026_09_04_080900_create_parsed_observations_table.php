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
        Schema::create('parsed_observations', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignUuid('parsed_artifact_id')->constrained('parsed_artifacts')->cascadeOnDelete();
            $table->unsignedBigInteger('source_row');
            $table->string('record_type', 32);
            $table->string('source_record_id', 128);
            $table->string('element_type', 128);
            $table->string('status', 64);
            $table->char('row_sha256', 64);
            $table->json('fields');
            $table->timestampTz('created_at');

            $table->unique(['parsed_artifact_id', 'source_row']);
            $table->index(['parsed_artifact_id', 'record_type']);
            $table->index(['parsed_artifact_id', 'source_record_id']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('parsed_observations');
    }
};
