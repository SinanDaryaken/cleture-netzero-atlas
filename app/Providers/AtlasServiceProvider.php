<?php

namespace App\Providers;

use App\Application\Candidate\SourceNormalizerRegistry;
use App\Application\Contracts\CandidateContractRegistry;
use App\Application\Contracts\CandidateDiffRulesetLoader;
use App\Application\Contracts\CandidateDraftReader;
use App\Application\Contracts\CandidateDraftWriter;
use App\Application\Contracts\CandidateEntityMemberWriter;
use App\Application\Contracts\CandidateRecordMemberWriter;
use App\Application\Contracts\CandidateSchemaValidator;
use App\Application\Contracts\CanonicalJson;
use App\Application\Contracts\CatalogContractRegistry;
use App\Application\Contracts\CatalogSchemaValidator;
use App\Application\Contracts\CatalogSnapshotLoader;
use App\Application\Contracts\GeographyCatalogResolver;
use App\Application\Contracts\IngestionLedger;
use App\Application\Contracts\NormalizationLedger;
use App\Application\Contracts\NormalizedArtifactStorage;
use App\Application\Contracts\ParsedObservationReader;
use App\Application\Contracts\ParsingLedger;
use App\Application\Contracts\ProcessingArtifactStorage;
use App\Application\Contracts\RawAssetStorage;
use App\Application\Contracts\RawAssetStreamReader;
use App\Application\Contracts\UnitCatalogResolver;
use App\Application\Ingestion\SourceAdapterRegistry;
use App\Application\Ingestion\SourceParserRegistry;
use App\Domain\Catalog\CatalogSnapshotIntegrity;
use App\Infrastructure\Candidate\JsonCandidateDiffRulesetLoader;
use App\Infrastructure\Candidate\LaravelCandidateDraftReader;
use App\Infrastructure\Candidate\NdjsonCandidateDraftWriter;
use App\Infrastructure\Candidate\NdjsonCandidateEntityMemberWriter;
use App\Infrastructure\Candidate\NdjsonCandidateRecordMemberWriter;
use App\Infrastructure\Candidate\Rfc8785CanonicalJson;
use App\Infrastructure\Catalog\LaravelCatalogSnapshotLoader;
use App\Infrastructure\Catalog\SnapshotGeographyCatalogResolver;
use App\Infrastructure\Catalog\SnapshotUnitCatalogResolver;
use App\Infrastructure\Contracts\OpisCandidateSchemaValidator;
use App\Infrastructure\Contracts\OpisCatalogSchemaValidator;
use App\Infrastructure\Contracts\PinnedCandidateContractRegistry;
use App\Infrastructure\Contracts\PinnedCatalogContractRegistry;
use App\Infrastructure\Persistence\EloquentIngestionLedger;
use App\Infrastructure\Persistence\EloquentNormalizationLedger;
use App\Infrastructure\Persistence\EloquentParsingLedger;
use App\Infrastructure\Sources\Ademe\AdemeCandidateNormalizer;
use App\Infrastructure\Sources\Ademe\AdemeCsvParser;
use App\Infrastructure\Sources\Ademe\AdemeSourceAdapter;
use App\Infrastructure\Storage\LaravelNormalizedArtifactStorage;
use App\Infrastructure\Storage\LaravelParsedObservationReader;
use App\Infrastructure\Storage\LaravelProcessingArtifactStorage;
use App\Infrastructure\Storage\LaravelRawAssetStorage;
use App\Infrastructure\Storage\LaravelRawAssetStreamReader;
use Illuminate\Filesystem\FilesystemManager;
use Illuminate\Http\Client\Factory;
use Illuminate\Support\ServiceProvider;

final class AtlasServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        $this->app->singleton(
            CandidateContractRegistry::class,
            fn (): CandidateContractRegistry => new PinnedCandidateContractRegistry(
                manifestPath: config('atlas.contracts.candidate_manifest_path'),
            ),
        );

        $this->app->singleton(
            CatalogContractRegistry::class,
            fn (): CatalogContractRegistry => new PinnedCatalogContractRegistry(
                manifestPath: config('atlas.contracts.catalog_manifest_path'),
            ),
        );

        $this->app->bind(IngestionLedger::class, EloquentIngestionLedger::class);
        $this->app->bind(NormalizationLedger::class, EloquentNormalizationLedger::class);
        $this->app->bind(ParsingLedger::class, EloquentParsingLedger::class);
        $this->app->bind(CandidateDraftWriter::class, NdjsonCandidateDraftWriter::class);
        $this->app->bind(CandidateDraftReader::class, LaravelCandidateDraftReader::class);
        $this->app->bind(CandidateEntityMemberWriter::class, NdjsonCandidateEntityMemberWriter::class);
        $this->app->bind(CandidateRecordMemberWriter::class, NdjsonCandidateRecordMemberWriter::class);
        $this->app->bind(CandidateSchemaValidator::class, OpisCandidateSchemaValidator::class);
        $this->app->bind(CanonicalJson::class, Rfc8785CanonicalJson::class);
        $this->app->bind(CatalogSchemaValidator::class, OpisCatalogSchemaValidator::class);
        $this->app->bind(GeographyCatalogResolver::class, SnapshotGeographyCatalogResolver::class);
        $this->app->bind(UnitCatalogResolver::class, SnapshotUnitCatalogResolver::class);
        $this->app->bind(ParsedObservationReader::class, LaravelParsedObservationReader::class);
        $this->app->bind(RawAssetStreamReader::class, LaravelRawAssetStreamReader::class);

        $this->app->singleton(
            CandidateDiffRulesetLoader::class,
            fn (): CandidateDiffRulesetLoader => new JsonCandidateDiffRulesetLoader(
                path: config('atlas.rulesets.candidate_diff.path'),
                expectedSha256: config('atlas.rulesets.candidate_diff.sha256'),
            ),
        );

        $this->app->singleton(RawAssetStorage::class, function ($app): RawAssetStorage {
            return new LaravelRawAssetStorage(
                filesystems: $app->make(FilesystemManager::class),
                disk: config('atlas.storage.raw_disk'),
            );
        });

        $this->app->singleton(
            ProcessingArtifactStorage::class,
            function ($app): ProcessingArtifactStorage {
                return new LaravelProcessingArtifactStorage(
                    filesystems: $app->make(FilesystemManager::class),
                    disk: config('atlas.storage.processing_disk'),
                );
            },
        );

        $this->app->singleton(
            NormalizedArtifactStorage::class,
            function ($app): NormalizedArtifactStorage {
                return new LaravelNormalizedArtifactStorage(
                    filesystems: $app->make(FilesystemManager::class),
                    disk: config('atlas.storage.processing_disk'),
                );
            },
        );

        $this->app->singleton(
            CatalogSnapshotLoader::class,
            fn ($app): CatalogSnapshotLoader => new LaravelCatalogSnapshotLoader(
                filesystems: $app->make(FilesystemManager::class),
                schemaValidator: $app->make(CatalogSchemaValidator::class),
                integrity: $app->make(CatalogSnapshotIntegrity::class),
                disk: config('atlas.storage.catalog_disk'),
                snapshotConfigurations: config('atlas.catalogs.snapshots'),
            ),
        );

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

        $this->app->singleton(SourceParserRegistry::class, function ($app): SourceParserRegistry {
            return new SourceParserRegistry([
                $app->make(AdemeCsvParser::class),
            ]);
        });

        $this->app->singleton(SourceNormalizerRegistry::class, function ($app): SourceNormalizerRegistry {
            return new SourceNormalizerRegistry([
                $app->make(AdemeCandidateNormalizer::class),
            ]);
        });
    }
}
