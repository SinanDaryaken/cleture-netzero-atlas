<?php

namespace App\Application\Contracts;

use App\Domain\Catalog\CurrentApprovalObservation;
use stdClass;

interface CurrentApprovalClient
{
    public function check(string $deliverySha256, stdClass $expectedResolution, stdClass $baseCatalog): CurrentApprovalObservation;
}
