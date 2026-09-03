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
        Schema::create('ingestion_runs', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignUuid('source_id')->constrained('sources')->restrictOnDelete();
            $table->foreignUuid('source_release_id')->constrained('source_releases')->restrictOnDelete();
            $table->char('idempotency_key', 64)->unique();
            $table->string('phase', 32)->default('acquire_raw');
            $table->string('status', 32)->default('running');
            $table->timestampTz('started_at');
            $table->timestampTz('completed_at')->nullable();
            $table->string('failure_code')->nullable();
            $table->text('failure_message')->nullable();
            $table->json('metrics')->nullable();
            $table->timestamps();

            $table->index(['source_id', 'status', 'started_at']);
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('ingestion_runs');
    }
};
