<?php

namespace App\Application\Contracts;

use App\Domain\Candidate\LicenseSnapshot;

interface LicenseSnapshotLoader
{
    public function load(string $descriptorPath, string $descriptorSha256, array $source): LicenseSnapshot;
}
