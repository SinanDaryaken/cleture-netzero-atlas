<?php

namespace App\Domain\Catalog;

/** A checked-at observation, never a reusable authorization or finalization token. */
final readonly class CurrentApprovalObservation
{
    public function __construct(
        public string $deliverySha256,
        public string $requestId,
        public string $stateSha256,
        public string $checkedAt,
    ) {}

    public function receipt(): array
    {
        return ['status' => 'current_at_check', 'delivery_sha256' => $this->deliverySha256,
            'request_id' => $this->requestId, 'state_sha256' => $this->stateSha256, 'checked_at' => $this->checkedAt,
            'validity' => 'checked_at_only', 'recheck_before_use' => true, 'cache_allowed' => false,
            'automatic_mapping_allowed' => false, 'usage_allowed' => false, 'publish_allowed' => false];
    }
}
