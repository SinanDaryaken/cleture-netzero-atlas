<?php

namespace App\Providers;

use App\Application\Candidate\SourceNormalizerRegistry;
use App\Application\Catalog\TransferAtlasDelivery;
use App\Application\Contracts\AtlasDeliveryStore;
use App\Application\Contracts\AtlasDeliveryVerifier;
use App\Application\Contracts\CandidateBuildRepository;
use App\Application\Contracts\CandidateContractRegistry;
use App\Application\Contracts\CandidateDiffRulesetLoader;
use App\Application\Contracts\CandidateDraftReader;
use App\Application\Contracts\CandidateDraftWriter;
use App\Application\Contracts\CandidateEntityMemberWriter;
use App\Application\Contracts\CandidateEntityReader;
use App\Application\Contracts\CandidateMappingPolicyLoader;
use App\Application\Contracts\CandidatePackageIdentityLedger;
use App\Application\Contracts\CandidatePackageLedger;
use App\Application\Contracts\CandidatePackageStorage;
use App\Application\Contracts\CandidateRecordMemberWriter;
use App\Application\Contracts\CandidateReleaseComparison;
use App\Application\Contracts\CandidateSchemaValidator;
use App\Application\Contracts\CandidateValidationRulesetLoader;
use App\Application\Contracts\CanonicalJson;
use App\Application\Contracts\CatalogContractRegistry;
use App\Application\Contracts\CatalogSchemaValidator;
use App\Application\Contracts\CatalogSnapshotLoader;
use App\Application\Contracts\CurrentApprovalClient;
use App\Application\Contracts\DeliveredResolutionApproval;
use App\Application\Contracts\GeographyCatalogResolver;
use App\Application\Contracts\IngestionLedger;
use App\Application\Contracts\LicenseSnapshotLoader;
use App\Application\Contracts\NormalizationLedger;
use App\Application\Contracts\NormalizedArtifactStorage;
use App\Application\Contracts\ParsedObservationReader;
use App\Application\Contracts\ParsingLedger;
use App\Application\Contracts\PreviousCandidatePackageReader;
use App\Application\Contracts\ProcessingArtifactStorage;
use App\Application\Contracts\RawAssetStorage;
use App\Application\Contracts\RawAssetStreamReader;
use App\Application\Contracts\UnitCatalogResolver;
use App\Application\Ingestion\SourceAdapterRegistry;
use App\Application\Ingestion\SourceParserRegistry;
use App\Domain\Catalog\CatalogSnapshotIntegrity;
use App\Domain\Catalog\SortedCatalogJson;
use App\Infrastructure\Candidate\DiskCandidateReleaseComparison;
use App\Infrastructure\Candidate\JsonCandidateDiffRulesetLoader;
use App\Infrastructure\Candidate\JsonCandidateValidationRulesetLoader;
use App\Infrastructure\Candidate\LaravelCandidateDraftReader;
use App\Infrastructure\Candidate\LaravelLicenseSnapshotLoader;
use App\Infrastructure\Candidate\NdjsonCandidateDraftWriter;
use App\Infrastructure\Candidate\NdjsonCandidateEntityMemberWriter;
use App\Infrastructure\Candidate\NdjsonCandidateRecordMemberWriter;
use App\Infrastructure\Candidate\PinnedCandidateMappingPolicy;
use App\Infrastructure\Candidate\Rfc8785CanonicalJson;
use App\Infrastructure\Candidate\StoredPreviousCandidatePackageReader;
use App\Infrastructure\Candidate\VerifiedCandidateEntityReader;
use App\Infrastructure\Catalog\DeliveryCatalogSnapshotLoader;
use App\Infrastructure\Catalog\HttpCurrentApprovalClient;
use App\Infrastructure\Catalog\LaravelCatalogSnapshotLoader;
use App\Infrastructure\Catalog\SnapshotGeographyCatalogResolver;
use App\Infrastructure\Catalog\SnapshotUnitCatalogResolver;
use App\Infrastructure\Catalog\VerifyAtlasDelivery;
use App\Infrastructure\Catalog\VerifyDeliveredResolution;
use App\Infrastructure\Contracts\OpisCandidateSchemaValidator;
use App\Infrastructure\Contracts\OpisCatalogSchemaValidator;
use App\Infrastructure\Contracts\PinnedCandidateContractRegistry;
use App\Infrastructure\Contracts\PinnedCatalogContractRegistry;
use App\Infrastructure\Contracts\PinnedCurrentApprovalContracts;
use App\Infrastructure\Contracts\PinnedDeliveryContracts;
use App\Infrastructure\Persistence\EloquentCandidateBuildRepository;
use App\Infrastructure\Persistence\EloquentCandidatePackageIdentityLedger;
use App\Infrastructure\Persistence\EloquentCandidatePackageLedger;
use App\Infrastructure\Persistence\EloquentIngestionLedger;
use App\Infrastructure\Persistence\EloquentNormalizationLedger;
use App\Infrastructure\Persistence\EloquentParsingLedger;
use App\Infrastructure\Sources\Ademe\AdemeCandidateNormalizer;
use App\Infrastructure\Sources\Ademe\AdemeCsvParser;
use App\Infrastructure\Sources\Ademe\AdemeSourceAdapter;
use App\Infrastructure\Storage\LaravelAtlasDeliveryStore;
use App\Infrastructure\Storage\LaravelCandidatePackageStorage;
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
        $this->app->bind(DeliveredResolutionApproval::class, VerifyDeliveredResolution::class);
        $this->app->singleton(PinnedCurrentApprovalContracts::class,
            fn () => new PinnedCurrentApprovalContracts(base_path('resources/contracts/netzero-admin/current-approval-v1')));
        $this->app->bind(CurrentApprovalClient::class, HttpCurrentApprovalClient::class);
        $this->app->bind(HttpCurrentApprovalClient::class, fn ($app) => new HttpCurrentApprovalClient(
            $app->make(Factory::class), $app->make(SortedCatalogJson::class),
            $app->make(PinnedCurrentApprovalContracts::class), config('atlas.current_approval'),
        ));
        $this->app->bind(AtlasDeliveryVerifier::class, VerifyAtlasDelivery::class);
        $this->app->singleton(PinnedDeliveryContracts::class,
            fn () => new PinnedDeliveryContracts(base_path('resources/contracts/netzero-admin/delivery-v1')));
        $this->app->bind(AtlasDeliveryStore::class,
            fn ($app) => new LaravelAtlasDeliveryStore($app->make(FilesystemManager::class), config('atlas.storage.catalog_disk')));
        $this->app->bind(CandidateMappingPolicyLoader::class, fn ($app) => $app->make(PinnedCandidateMappingPolicy::class));
        $this->app->bind(CandidateEntityReader::class, VerifiedCandidateEntityReader::class);
        $this->app->bind(CandidateReleaseComparison::class, DiskCandidateReleaseComparison::class);
        $this->app->bind(PreviousCandidatePackageReader::class, StoredPreviousCandidatePackageReader::class);
        $this->app->bind(CandidatePackageIdentityLedger::class, EloquentCandidatePackageIdentityLedger::class);
        $this->app->singleton(CandidateValidationRulesetLoader::class,
            fn () => new JsonCandidateValidationRulesetLoader(config('atlas.rulesets.candidate_validation.path'), config('atlas.rulesets.candidate_validation.sha256')));
        $this->app->singleton(PinnedCandidateMappingPolicy::class,
            fn () => new PinnedCandidateMappingPolicy(config('atlas.rulesets.candidate_mapping.path'), config('atlas.rulesets.candidate_mapping.sha256')));
        $this->app->bind(LicenseSnapshotLoader::class,
            fn ($app) => new LaravelLicenseSnapshotLoader($app->make(FilesystemManager::class), config('atlas.storage.processing_disk')));
        $this->app->bind(CandidateBuildRepository::class,
            fn ($app) => new EloquentCandidateBuildRepository($app->make(CanonicalJson::class), $app->make(FilesystemManager::class), config('atlas.storage.processing_disk')));
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
        $this->app->bind(CandidatePackageLedger::class, EloquentCandidatePackageLedger::class);
        $this->app->bind(CandidateRecordMemberWriter::class, NdjsonCandidateRecordMemberWriter::class);
        $this->app->bind(CandidateSchemaValidator::class, OpisCandidateSchemaValidator::class);
        $this->app->bind(CanonicalJson::class, Rfc8785CanonicalJson::class);
        $this->app->bind(CatalogSchemaValidator::class, OpisCatalogSchemaValidator::class);
        $this->app->bind(GeographyCatalogResolver::class, SnapshotGeographyCatalogResolver::class);
        $this->app->bind(UnitCatalogResolver::class, SnapshotUnitCatalogResolver::class);
        $this->app->bind(ParsedObservationReader::class, LaravelParsedObservationReader::class);
        $this->app->bind(RawAssetStreamReader::class, LaravelRawAssetStreamReader::class);

        $this->app->singleton(
            CandidatePackageStorage::class,
            fn ($app): CandidatePackageStorage => new LaravelCandidatePackageStorage(
                filesystems: $app->make(FilesystemManager::class),
                disk: config('atlas.storage.candidate_disk'),
            ),
        );

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
            fn ($app): CatalogSnapshotLoader => config('atlas.catalogs.delivery.sha256') !== null
                ? new DeliveryCatalogSnapshotLoader(
                    $app->make(TransferAtlasDelivery::class), config('atlas.catalogs.delivery.sha256'), config('atlas.catalogs.delivery.pins'),
                ) : new LaravelCatalogSnapshotLoader(
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
