<?php

namespace App\Application\Catalog;

use App\Application\Contracts\AtlasDeliveryStore;
use App\Application\Contracts\AtlasDeliveryVerifier;
use App\Domain\Catalog\VerifiedAtlasDelivery;

final readonly class TransferAtlasDelivery
{
    public function __construct(private AtlasDeliveryVerifier $verify, private AtlasDeliveryStore $store) {}

    /** @param callable(string, int): string $readSource */
    public function transfer(string $expectedSha256, callable $readSource): VerifiedAtlasDelivery
    {
        $source = $this->verify->verify($expectedSha256, $readSource);
        foreach ($source->manifest->artifacts as $artifact) {
            $this->store->putImmutable($expectedSha256, $artifact->object_path, $source->artifacts[$artifact->name]);
        }
        // Verify all target bytes and semantic links before exposing the final marker.
        $this->verify->verify($expectedSha256, fn (string $path, int $limit): string => $path === 'manifest.json'
            ? $source->manifestBytes : $this->store->read($expectedSha256, $path, $limit));
        $this->store->putImmutable($expectedSha256, 'manifest.json', $source->manifestBytes);

        return $this->read($expectedSha256);
    }

    public function read(string $expectedSha256): VerifiedAtlasDelivery
    {
        return $this->verify->verify($expectedSha256, fn (string $path, int $limit): string => $this->store->read($expectedSha256, $path, $limit));
    }
}
