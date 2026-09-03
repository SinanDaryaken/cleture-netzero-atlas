<?php

namespace App\Infrastructure\Sources\Ademe;

use App\Application\Contracts\SourceAcquisitionAdapter;
use App\Domain\Ingestion\DownloadedAsset;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use App\Domain\Ingestion\Exceptions\SourceTemporarilyUnavailable;
use App\Domain\Ingestion\SourceRelease;
use DateTimeImmutable;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Factory;
use Illuminate\Http\Client\RequestException;
use Illuminate\Http\Client\Response;
use Throwable;

final readonly class AdemeSourceAdapter implements SourceAcquisitionAdapter
{
    private const DATASET_ID = 'base-carboner';

    public function __construct(
        private Factory $http,
        private string $datasetUrl,
        private int $connectTimeoutSeconds,
        private int $timeoutSeconds,
    ) {}

    public function sourceCode(): string
    {
        return 'ADEME';
    }

    public function discover(): SourceRelease
    {
        $metadata = $this->getJson($this->datasetUrl);
        $this->assertMetadataContract($metadata);

        /** @var array<string, mixed> $file */
        $file = $metadata['file'];
        $fileName = $file['name'];
        $version = $this->extractVersion($fileName);
        $dataFiles = $this->getJson($this->datasetUrl.'/data-files');
        $assetUrl = $this->originalAssetUrl($dataFiles, $fileName);
        $sourceUpdatedAt = $this->parseDate($metadata['dataUpdatedAt'] ?? null);

        $revisionPayload = implode('|', [
            self::DATASET_ID,
            $fileName,
            $file['md5'],
            (string) $file['size'],
            (string) $metadata['count'],
            (string) ($metadata['dataUpdatedAt'] ?? ''),
        ]);

        return new SourceRelease(
            sourceCode: $this->sourceCode(),
            datasetId: self::DATASET_ID,
            version: $version,
            revisionSha256: hash('sha256', $revisionPayload),
            reportedRowCount: $metadata['count'],
            assetUrl: $assetUrl,
            fileName: $fileName,
            fileSize: $file['size'],
            upstreamChecksumAlgorithm: 'md5',
            upstreamChecksum: mb_strtolower($file['md5']),
            licenseTitle: $metadata['license']['title'],
            sourceUpdatedAt: $sourceUpdatedAt,
            metadata: [
                'publisher' => 'ADEME',
                'source_name' => 'ADEME Base Carbone',
                'landing_page' => 'https://data.ademe.fr/datasets/base-carboner',
                'metadata_url' => $this->datasetUrl,
            ],
        );
    }

    public function download(SourceRelease $release): DownloadedAsset
    {
        if ($release->sourceCode !== $this->sourceCode() || $release->datasetId !== self::DATASET_ID) {
            throw new SourceContractViolation('ADEME adapter received a foreign release.');
        }

        $temporaryPath = tempnam(sys_get_temp_dir(), 'atlas-ademe-');

        if ($temporaryPath === false) {
            throw new SourceTemporarilyUnavailable('A temporary ADEME download file could not be created.');
        }

        $downloadCompleted = false;

        try {
            $response = $this->http
                ->withHeaders(['Accept' => 'text/csv,application/octet-stream'])
                ->withUserAgent('Cleture-NetZero-Atlas/1.0')
                ->connectTimeout($this->connectTimeoutSeconds)
                ->timeout(max($this->timeoutSeconds, 120))
                ->retry(
                    [500, 1500, 3000],
                    when: static fn (Throwable $exception): bool => self::isTransient($exception),
                )
                ->get($release->assetUrl);

            if (! $response->successful()) {
                throw $this->responseException($response, 'download');
            }

            if (file_put_contents($temporaryPath, $response->body(), LOCK_EX) === false) {
                throw new SourceTemporarilyUnavailable('ADEME download could not be written to temporary storage.');
            }

            $fileSize = filesize($temporaryPath);
            $md5 = hash_file('md5', $temporaryPath);
            $sha256 = hash_file('sha256', $temporaryPath);

            if (! is_int($fileSize) || ! is_string($md5) || ! is_string($sha256)) {
                throw new SourceTemporarilyUnavailable('ADEME download identity could not be calculated.');
            }

            if ($fileSize !== $release->fileSize) {
                throw new SourceContractViolation(
                    "ADEME file size mismatch: expected {$release->fileSize}, received {$fileSize}.",
                );
            }

            if (! hash_equals($release->upstreamChecksum, $md5)) {
                throw new SourceContractViolation('ADEME upstream MD5 verification failed.');
            }

            $asset = new DownloadedAsset(
                temporaryPath: $temporaryPath,
                fileName: $release->fileName,
                sourceUrl: $release->assetUrl,
                mediaType: $response->header('Content-Type'),
                fileSize: $fileSize,
                sha256: $sha256,
                downloadedAt: now()->toDateTimeImmutable(),
            );
            $downloadCompleted = true;

            return $asset;
        } catch (ConnectionException $exception) {
            throw new SourceTemporarilyUnavailable(
                'ADEME source file could not be reached.',
                previous: $exception,
            );
        } catch (RequestException $exception) {
            throw $this->httpException($exception->response, $exception);
        } finally {
            if (! $downloadCompleted && is_file($temporaryPath)) {
                unlink($temporaryPath);
            }
        }
    }

    /**
     * @return array<array-key, mixed>
     */
    private function getJson(string $url): array
    {
        try {
            $response = $this->http
                ->acceptJson()
                ->withUserAgent('Cleture-NetZero-Atlas/1.0')
                ->connectTimeout($this->connectTimeoutSeconds)
                ->timeout($this->timeoutSeconds)
                ->retry(
                    [250, 750, 1500],
                    when: static fn (Throwable $exception): bool => self::isTransient($exception),
                )
                ->get($url);
        } catch (ConnectionException $exception) {
            throw new SourceTemporarilyUnavailable(
                'ADEME could not be reached.',
                previous: $exception,
            );
        } catch (RequestException $exception) {
            throw $this->httpException($exception->response, $exception);
        }

        if ($response->status() === 429 || $response->serverError()) {
            throw new SourceTemporarilyUnavailable(
                "ADEME returned HTTP {$response->status()}.",
            );
        }

        if (! $response->successful()) {
            throw new SourceContractViolation(
                "ADEME rejected the discovery request with HTTP {$response->status()}.",
            );
        }

        $payload = $response->json();

        if (! is_array($payload)) {
            throw new SourceContractViolation('ADEME returned invalid JSON.');
        }

        return $payload;
    }

    private static function isTransient(Throwable $exception): bool
    {
        if ($exception instanceof ConnectionException) {
            return true;
        }

        if (! $exception instanceof RequestException) {
            return false;
        }

        return $exception->response->status() === 429 || $exception->response->serverError();
    }

    private function httpException(Response $response, RequestException $exception): Throwable
    {
        if ($response->status() === 429 || $response->serverError()) {
            return new SourceTemporarilyUnavailable(
                "ADEME returned HTTP {$response->status()}.",
                previous: $exception,
            );
        }

        return new SourceContractViolation(
            "ADEME rejected the discovery request with HTTP {$response->status()}.",
            previous: $exception,
        );
    }

    private function responseException(Response $response, string $operation): Throwable
    {
        if ($response->status() === 429 || $response->serverError()) {
            return new SourceTemporarilyUnavailable(
                "ADEME {$operation} returned HTTP {$response->status()}.",
            );
        }

        return new SourceContractViolation(
            "ADEME {$operation} was rejected with HTTP {$response->status()}.",
        );
    }

    /**
     * @param  array<array-key, mixed>  $metadata
     */
    private function assertMetadataContract(array $metadata): void
    {
        if (($metadata['id'] ?? null) !== self::DATASET_ID) {
            throw new SourceContractViolation('ADEME dataset identity changed.');
        }

        if (($metadata['status'] ?? null) !== 'finalized') {
            throw new SourceTemporarilyUnavailable('ADEME dataset is not finalized.');
        }

        if (! is_int($metadata['count'] ?? null) || $metadata['count'] < 1) {
            throw new SourceContractViolation('ADEME row count is missing or invalid.');
        }

        $file = $metadata['file'] ?? null;

        if (! is_array($file)
            || ! is_string($file['name'] ?? null)
            || ! is_int($file['size'] ?? null)
            || $file['size'] < 1
            || ! is_string($file['md5'] ?? null)
            || preg_match('/^[a-fA-F0-9]{32}$/', $file['md5']) !== 1
        ) {
            throw new SourceContractViolation('ADEME source file identity is invalid.');
        }

        $license = $metadata['license'] ?? null;

        if (! is_array($license)
            || ! is_string($license['title'] ?? null)
            || ! str_contains($license['title'], 'Licence Ouverte')
        ) {
            throw new SourceContractViolation('ADEME open-license contract changed.');
        }
    }

    private function extractVersion(string $fileName): string
    {
        if (preg_match('/_V(\d+(?:\.\d+)*)\.csv$/i', $fileName, $matches) !== 1) {
            throw new SourceContractViolation('ADEME release version could not be identified.');
        }

        return $matches[1];
    }

    /**
     * @param  array<array-key, mixed>  $dataFiles
     */
    private function originalAssetUrl(array $dataFiles, string $fileName): string
    {
        if (basename($fileName) !== $fileName) {
            throw new SourceContractViolation('ADEME source filename is unsafe.');
        }

        foreach ($dataFiles as $dataFile) {
            if (! is_array($dataFile)
                || ($dataFile['key'] ?? null) !== 'original'
                || ($dataFile['name'] ?? null) !== $fileName
            ) {
                continue;
            }

            $url = $dataFile['url'] ?? null;

            if (is_string($url)
                && filter_var($url, FILTER_VALIDATE_URL) !== false
                && parse_url($url, PHP_URL_SCHEME) === 'https'
                && parse_url($url, PHP_URL_HOST) === 'data.ademe.fr'
            ) {
                return $url;
            }
        }

        throw new SourceContractViolation('ADEME original source file is unavailable.');
    }

    private function parseDate(mixed $value): ?DateTimeImmutable
    {
        if (! is_string($value) || $value === '') {
            return null;
        }

        try {
            return new DateTimeImmutable($value);
        } catch (Throwable) {
            return null;
        }
    }
}
