<?php

namespace Tests\Feature;

use App\Application\Contracts\AtlasDeliveryStore;
use App\Infrastructure\Contracts\PinnedCurrentApprovalContracts;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\Http;
use Tests\Support\CurrentApprovalFixture as Peer;
use Tests\Support\DeliveryFixture;
use Tests\Support\InMemoryDeliveryStore;
use Tests\TestCase;

final class ApprovalReadinessTest extends TestCase
{
    public function test_missing_settings_and_delivery_are_reported_without_network_or_credentials(): void
    {
        Http::preventStrayRequests();
        config(['atlas.current_approval' => [...Peer::settings(), 'enabled' => false]]);
        [$exit, $report, $output] = $this->inspect();
        $this->assertSame(1, $exit);
        $this->assertFalse($report['local_query_prerequisites_met']);
        $this->assertSame(['atlas_connection_not_configured', 'independent_delivery_pin_required'], $report['blockers']);
        $this->assertTrue($report['query_schema_pins_verified']);
        $this->assertStringNotContainsString(Peer::SECRET, $output);
        $this->assertStringNotContainsString(Peer::KEY, $output);
        $this->assertStringNotContainsString(Peer::URL, $output);
        Http::assertNothingSent();
    }

    public function test_catalog_only_delivery_cannot_pass_resolution_preflight(): void
    {
        Http::preventStrayRequests();
        config(['atlas.current_approval' => Peer::settings()]);
        [$package, $store] = $this->stored(null);
        [$exit, $report] = $this->inspect(['sha256' => $package['hash']]);
        $this->assertSame(1, $exit);
        $this->assertTrue($report['stored_delivery_verified']);
        $this->assertFalse($report['resolution_present']);
        $this->assertSame(['approved_resolution_delivery_required'], $report['blockers']);
        $this->assertSame([], $store->writes);
        Http::assertNothingSent();
    }

    public function test_matching_synthetic_delivery_passes_local_checks_but_never_grants_usage(): void
    {
        Http::preventStrayRequests();
        config(['atlas.current_approval' => Peer::settings()]);
        [$package, $store] = $this->stored('new_unit');
        $path = tempnam(sys_get_temp_dir(), 'atlas-ready-');
        file_put_contents($path, DeliveryFixture::json($package['manifest']['resolution']));
        try {
            [$exit, $report] = $this->inspect(['sha256' => $package['hash'], '--expected' => $path]);
            $this->assertSame(0, $exit);
            $this->assertSame('local_preflight_passed', $report['status']);
            $this->assertTrue($report['expected_resolution_verified']);
            $this->assertFalse($report['connection']['network_checked']);
            $this->assertFalse($report['connection']['admin_grants_verified']);
            foreach (['current_approval_verified', 'automatic_mapping_allowed', 'usage_allowed', 'publish_allowed'] as $field) {
                $this->assertFalse($report[$field]);
            }
            $this->assertContains('admin_atomic_finalization_contract', $report['remaining_external_checks']);
            $this->assertSame([], $store->writes);
        } finally {
            unlink($path);
        }
        Http::assertNothingSent();
    }

    public function test_missing_changed_expected_and_changed_stored_bytes_are_detected_on_each_read(): void
    {
        Http::preventStrayRequests();
        config(['atlas.current_approval' => Peer::settings()]);
        [$package, $store] = $this->stored('alias');
        [$exit, $report] = $this->inspect(['sha256' => $package['hash']]);
        $this->assertSame(1, $exit);
        $this->assertSame(['independent_expected_resolution_required'], $report['blockers']);
        $expected = $package['manifest']['resolution'];
        $expected['decision_sha256'] = str_repeat('f', 64);
        $path = tempnam(sys_get_temp_dir(), 'atlas-ready-');
        file_put_contents($path, DeliveryFixture::json($expected));
        try {
            [$exit, $report] = $this->inspect(['sha256' => $package['hash'], '--expected' => $path]);
            $this->assertSame(1, $exit);
            $this->assertSame(['expected_resolution_verification_failed'], $report['blockers']);
            $store->objects[$package['hash'].'/manifest.json'] .= "\n";
            [$exit, $report] = $this->inspect(['sha256' => $package['hash'], '--expected' => $path]);
            $this->assertSame(1, $exit);
            $this->assertSame(['stored_delivery_verification_failed'], $report['blockers']);
        } finally {
            unlink($path);
        }
        Http::assertNothingSent();
    }

    public function test_unsafe_endpoint_and_missing_schema_pins_are_not_reported_ready(): void
    {
        Http::preventStrayRequests();
        config(['atlas.current_approval' => [...Peer::settings(),
            'endpoint' => 'https://private-user:private-password@admin.example.test/internal/v1/atlas/current-approval']]);
        $this->app->instance(PinnedCurrentApprovalContracts::class, new PinnedCurrentApprovalContracts('/missing-approval-contracts'));
        [$exit, $report, $output] = $this->inspect();
        $this->assertSame(1, $exit);
        $this->assertContains('atlas_connection_not_configured', $report['blockers']);
        $this->assertContains('current_approval_schema_pin_failed', $report['blockers']);
        $this->assertStringNotContainsString('private-password', $output);
        $this->assertStringNotContainsString('private-user', $output);
        Http::assertNothingSent();
    }

    private function stored(?string $type): array
    {
        $package = (new DeliveryFixture($type))->package();
        $store = new InMemoryDeliveryStore;
        foreach ($package['objects'] as $path => $bytes) {
            $store->objects[$package['hash'].'/'.$path] = $bytes;
        }
        $this->app->instance(AtlasDeliveryStore::class, $store);

        return [$package, $store];
    }

    private function inspect(array $arguments = []): array
    {
        $exit = Artisan::call('atlas:catalog:approval-readiness', $arguments);
        $output = Artisan::output();

        return [$exit, json_decode($output, true, 64, JSON_THROW_ON_ERROR), $output];
    }
}
