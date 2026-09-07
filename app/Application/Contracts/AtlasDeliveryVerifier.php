<?php

namespace App\Application\Contracts;

use App\Domain\Catalog\VerifiedAtlasDelivery;

interface AtlasDeliveryVerifier
{
    /** @param callable(string, int): string $read */
    public function verify(string $expectedSha256, callable $read): VerifiedAtlasDelivery;
}
