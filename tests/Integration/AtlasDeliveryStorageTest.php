<?php

namespace Tests\Integration;

use App\Application\Catalog\TransferAtlasDelivery;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use App\Infrastructure\Catalog\VerifyAtlasDelivery;
use App\Infrastructure\Storage\LaravelAtlasDeliveryStore;
use Illuminate\Filesystem\FilesystemManager;
use Tests\Support\DeliveryFixture;
use Tests\TestCase;

/** Real MinIO, isolated disposable bucket. No database or application bucket writes. */
final class AtlasDeliveryStorageTest extends TestCase
{
    public function test_real_conditional_create_retry_readback_conflict_and_partial_delivery(): void
    {
        $bucket = 'atlas-delivery-test-'.bin2hex(random_bytes(8));
        $settings = config('filesystems.disks.atlas_catalogs');
        $this->assertSame('s3', $settings['driver']);
        config(['filesystems.disks.delivery_integration' => [...$settings, 'bucket' => $bucket]]);
        $manager = app(FilesystemManager::class);
        $disk = $manager->disk('delivery_integration');
        $client = $disk->getClient();
        $client->createBucket(['Bucket' => $bucket]);
        try {
            $package = (new DeliveryFixture)->package();
            $store = new LaravelAtlasDeliveryStore($manager, 'delivery_integration');
            $transfer = new TransferAtlasDelivery(app(VerifyAtlasDelivery::class), $store);
            $first = $transfer->transfer($package['hash'], DeliveryFixture::read($package['objects']));
            $retry = $transfer->transfer($package['hash'], DeliveryFixture::read($package['objects']));
            $this->assertSame($first->manifestBytes, $retry->manifestBytes);
            $this->assertSame($first->artifacts, $retry->artifacts);
            $this->assertCount(5, $retry->catalogs);
            $root = 'atlas-deliveries/sha256/'.$package['hash'].'/';
            $artifact = $package['manifest']['artifacts'][0];
            $client->putObject(['Bucket' => $bucket, 'Key' => $root.$artifact['object_path'], 'Body' => 'TEST conflict']);

            $this->invalid(fn () => $store->putImmutable($package['hash'], $artifact['object_path'], $package['objects'][$artifact['object_path']]));

            $this->assertSame('TEST conflict', (string) $client->getObject(['Bucket' => $bucket, 'Key' => $root.$artifact['object_path']])['Body']);
            $this->invalid(fn () => $transfer->read($package['hash']));
            $client->deleteObject(['Bucket' => $bucket, 'Key' => $root.'manifest.json']);
            $this->invalid(fn () => $transfer->read($package['hash']));
        } finally {
            // Cleanup is restricted to the exact randomly created test bucket.
            $this->assertStringStartsWith('atlas-delivery-test-', $bucket);
            $objects = $client->listObjectsV2(['Bucket' => $bucket])['Contents'] ?? [];
            foreach ($objects as $object) {
                $client->deleteObject(['Bucket' => $bucket, 'Key' => $object['Key']]);
            }
            $client->deleteBucket(['Bucket' => $bucket]);
            $manager->forgetDisk('delivery_integration');
        }
    }

    private function invalid(callable $operation): void
    {
        try {
            $operation();
            $this->fail('Invalid real-store delivery accepted.');
        } catch (CatalogContractViolation) {
            $this->addToAssertionCount(1);
        }
    }
}
