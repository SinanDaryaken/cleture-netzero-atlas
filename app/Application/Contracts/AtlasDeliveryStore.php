<?php

namespace App\Application\Contracts;

interface AtlasDeliveryStore
{
    public function read(string $deliverySha256, string $path, int $limit): string;

    public function putImmutable(string $deliverySha256, string $path, string $bytes): void;
}
