<?php

namespace App\Console\Commands;

use App\Application\Catalog\TransferAtlasDelivery;
use App\Infrastructure\Catalog\ExpectedResolutionFile;
use App\Infrastructure\Catalog\HttpCurrentApprovalClient;
use App\Infrastructure\Catalog\VerifyDeliveredResolution;
use App\Infrastructure\Contracts\PinnedCurrentApprovalContracts;
use Illuminate\Console\Command;
use Throwable;

final class AtlasApprovalReadinessCommand extends Command
{
    protected $signature = 'atlas:catalog:approval-readiness
        {sha256? : Independently trusted manifest SHA, read from Atlas storage}
        {--expected= : Independent exact expected resolution envelope file}';

    protected $description = 'Inspect local approval prerequisites without sending credentials, changing settings or granting usage';

    public function handle(
        TransferAtlasDelivery $deliveries,
        VerifyDeliveredResolution $resolutions,
        HttpCurrentApprovalClient $client,
        PinnedCurrentApprovalContracts $contracts,
        ExpectedResolutionFile $files,
    ): int {
        $connection = $client->connectionReadiness();
        $blockers = $connection['configuration_valid'] ? [] : ['atlas_connection_not_configured'];
        $schemasVerified = false;
        try {
            $contracts->verifyPins();
            $schemasVerified = true;
        } catch (Throwable) {
            $blockers[] = 'current_approval_schema_pin_failed';
        }
        $hash = $this->argument('sha256');
        $deliveryVerified = false;
        $resolutionPresent = false;
        $expectedVerified = false;
        if (! is_string($hash) || $hash === '') {
            $blockers[] = 'independent_delivery_pin_required';
        } else {
            try {
                $delivery = $deliveries->read($hash);
                $deliveryVerified = true;
                $resolutionPresent = $delivery->manifest->resolution !== null;
            } catch (Throwable) {
                // Storage exceptions can carry URLs and signed credentials; report only the failure class.
                $blockers[] = 'stored_delivery_verification_failed';
            }
            if ($deliveryVerified) {
                if (! $resolutionPresent) {
                    $blockers[] = 'approved_resolution_delivery_required';
                } elseif (! is_string($this->option('expected')) || $this->option('expected') === '') {
                    $blockers[] = 'independent_expected_resolution_required';
                } else {
                    try {
                        $resolutions->verifyExpected($delivery, $files->read($this->option('expected')));
                        $expectedVerified = true;
                    } catch (Throwable) {
                        $blockers[] = 'expected_resolution_verification_failed';
                    }
                }
            }
        }
        $localReady = $blockers === [];
        $this->line(json_encode([
            'status' => $localReady ? 'local_preflight_passed' : 'blocked',
            'local_query_prerequisites_met' => $localReady,
            'connection' => $connection, 'query_schema_pins_verified' => $schemasVerified,
            'stored_delivery_verified' => $deliveryVerified, 'resolution_present' => $resolutionPresent,
            'expected_resolution_verified' => $expectedVerified, 'blockers' => $blockers,
            'remaining_external_checks' => ['admin_key_source_grant', 'live_authenticated_current_approval',
                'authority_body_schemas', 'admin_atomic_finalization_contract'],
            'current_approval_verified' => false, 'automatic_mapping_allowed' => false,
            'usage_allowed' => false, 'publish_allowed' => false,
        ], JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT));

        return $localReady ? self::SUCCESS : self::FAILURE;
    }
}
