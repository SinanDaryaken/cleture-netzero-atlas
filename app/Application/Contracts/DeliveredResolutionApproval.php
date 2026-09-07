<?php

namespace App\Application\Contracts;

use App\Domain\Catalog\CurrentApprovalObservation;
use App\Domain\Catalog\VerifiedAtlasDelivery;
use stdClass;

interface DeliveredResolutionApproval
{
    public function inspectCurrentApproval(VerifiedAtlasDelivery $delivery, stdClass $expected): CurrentApprovalObservation;

    public function requireCurrentApproval(VerifiedAtlasDelivery $delivery, stdClass $expected): never;
}
