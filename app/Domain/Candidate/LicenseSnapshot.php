<?php

namespace App\Domain\Candidate;

final readonly class LicenseSnapshot
{
    public function __construct(public array $license, public array $source, public string $descriptorSha256) {}
}
