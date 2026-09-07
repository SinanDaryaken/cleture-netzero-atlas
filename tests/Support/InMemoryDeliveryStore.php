<?php

namespace Tests\Support;

use App\Application\Contracts\AtlasDeliveryStore;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;

final class InMemoryDeliveryStore implements AtlasDeliveryStore
{
    public array $objects = [];

    public array $writes = [];

    public ?int $failAfter = null;

    public function read(string $deliverySha256, string $path, int $limit): string
    {
        return $this->objects[$deliverySha256.'/'.$path] ?? throw new CatalogContractViolation('Partial delivery: artifact missing.');
    }

    public function putImmutable(string $deliverySha256, string $path, string $bytes): void
    {
        if ($this->failAfter !== null && count($this->writes) >= $this->failAfter) {
            throw new CatalogContractViolation('Simulated interrupted transfer.');
        }
        $key = $deliverySha256.'/'.$path;
        if (isset($this->objects[$key]) && $this->objects[$key] !== $bytes) {
            throw new CatalogContractViolation('Immutable conflict.');
        }
        $this->objects[$key] = $bytes;
        $this->writes[] = $path;
    }
}
