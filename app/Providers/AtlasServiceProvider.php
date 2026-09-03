<?php

namespace App\Providers;

use App\Application\Contracts\IngestionLedger;
use App\Application\Contracts\RawAssetStorage;
use App\Application\Ingestion\SourceAdapterRegistry;
use App\Infrastructure\Persistence\EloquentIngestionLedger;
use App\Infrastructure\Sources\Ademe\AdemeSourceAdapter;
use App\Infrastructure\Storage\LaravelRawAssetStorage;
use Illuminate\Filesystem\FilesystemManager;
use Illuminate\Http\Client\Factory;
use Illuminate\Support\ServiceProvider;

final class AtlasServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->bind(IngestionLedger::class, EloquentIngestionLedger::class);

        $this->app->singleton(RawAssetStorage::class, function ($app): RawAssetStorage {
            return new LaravelRawAssetStorage(
                filesystems: $app->make(FilesystemManager::class),
                disk: config('atlas.storage.raw_disk'),
            );
        });

        $this->app->singleton(AdemeSourceAdapter::class, function ($app): AdemeSourceAdapter {
            return new AdemeSourceAdapter(
                http: $app->make(Factory::class),
                datasetUrl: config('atlas.sources.ademe.dataset_url'),
                connectTimeoutSeconds: config('atlas.http.connect_timeout_seconds'),
                timeoutSeconds: config('atlas.http.timeout_seconds'),
            );
        });

        $this->app->singleton(SourceAdapterRegistry::class, function ($app): SourceAdapterRegistry {
            return new SourceAdapterRegistry([
                $app->make(AdemeSourceAdapter::class),
            ]);
        });
    }
}
