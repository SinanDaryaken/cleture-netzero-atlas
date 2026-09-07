<?php

namespace App\Application\Catalog;

use App\Application\Contracts\DeliveredResolutionApproval;
use App\Domain\Catalog\CurrentApprovalObservation;
use stdClass;

/** Each invocation re-reads the exact stored delivery and performs a new query. */
final readonly class CheckDeliveredResolutionApproval
{
    public function __construct(private TransferAtlasDelivery $deliveries, private DeliveredResolutionApproval $approval) {}

    public function inspect(string $deliverySha256, stdClass $expected): CurrentApprovalObservation
    {
        return $this->approval->inspectCurrentApproval($this->deliveries->read($deliverySha256), $expected);
    }

    public function requireForUse(string $deliverySha256, stdClass $expected): never
    {
        $this->approval->requireCurrentApproval($this->deliveries->read($deliverySha256), $expected);
    }
}
