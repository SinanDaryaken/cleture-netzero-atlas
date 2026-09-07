<?php

namespace App\Infrastructure\Storage;

use App\Application\Contracts\AtlasDeliveryStore;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use Aws\S3\Exception\S3Exception;
use Illuminate\Filesystem\AwsS3V3Adapter;
use Illuminate\Filesystem\FilesystemManager;
use Throwable;

/** S3 conditional creation is required; no check-then-overwrite fallback. */
final readonly class LaravelAtlasDeliveryStore implements AtlasDeliveryStore
{
    public function __construct(private FilesystemManager $filesystems, private string $disk) {}

    public function read(string $deliverySha256, string $path, int $limit): string
    {
        $key = $this->key($deliverySha256, $path);
        try {
            $stream = $this->filesystems->disk($this->disk)->readStream($key);
            if (! is_resource($stream)) {
                throw new CatalogContractViolation('Missing target delivery artifact.');
            }
            try {
                $bytes = stream_get_contents($stream, $limit + 1);
            } finally {
                fclose($stream);
            }
            if ($bytes === false || strlen($bytes) > $limit) {
                throw new CatalogContractViolation('Target artifact exceeds its byte bound.');
            }

            return $bytes;
        } catch (Throwable $exception) {
            throw new CatalogContractViolation('Target delivery read failed: '.$path, previous: $exception);
        }
    }

    public function putImmutable(string $deliverySha256, string $path, string $bytes): void
    {
        $key = $this->key($deliverySha256, $path);
        $contentHash = $path === 'manifest.json' ? $deliverySha256 : substr($path, strlen('objects/sha256/'));
        if (! hash_equals($contentHash, hash('sha256', $bytes))) {
            throw new CatalogContractViolation('Content does not match its immutable object address.');
        }
        $disk = $this->filesystems->disk($this->disk);
        if (! $disk instanceof AwsS3V3Adapter || ($disk->getConfig()['root'] ?? '') !== '') {
            throw new CatalogContractViolation('Delivery writes require an unprefixed S3 disk with conditional creation.');
        }
        try {
            $disk->getClient()->putObject(['Bucket' => $disk->getConfig()['bucket'], 'Key' => $key,
                'Body' => $bytes, 'ContentLength' => strlen($bytes), 'IfNoneMatch' => '*', 'ContentType' => 'application/octet-stream']);
        } catch (S3Exception $exception) {
            if ($exception->getStatusCode() !== 412) {
                throw new CatalogContractViolation('Conditional delivery write failed.', previous: $exception);
            }
        }
        if ($this->read($deliverySha256, $path, strlen($bytes)) !== $bytes) {
            throw new CatalogContractViolation('Immutable delivery conflict; existing bytes were preserved.');
        }
    }

    private function key(string $hash, string $path): string
    {
        if (! preg_match('/\A[a-f0-9]{64}\z/', $hash)
            || ! preg_match('#\A(?:manifest\.json|objects/sha256/[a-f0-9]{64})\z#', $path)) {
            throw new CatalogContractViolation('Unsafe delivery object key.');
        }

        return 'atlas-deliveries/sha256/'.$hash.'/'.$path;
    }
}
