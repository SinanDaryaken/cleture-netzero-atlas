<?php

namespace Tests\Integration;

use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use App\Infrastructure\Catalog\VerifyAtlasDelivery;
use App\Infrastructure\Catalog\VerifyDeliveredResolution;
use Illuminate\Support\Sleep;
use Tests\Support\CurrentApprovalFixture as Peer;
use Tests\Support\DeliveryFixture;
use Tests\TestCase;

final class CurrentApprovalHttpTest extends TestCase
{
    public function test_real_http_peer_checks_hmac_retry_rejection_and_disabled_redirects(): void
    {
        Sleep::fake();
        $process = proc_open([PHP_BINARY, base_path('tests/Support/current-approval-http-peer.php')],
            [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
        $this->assertIsResource($process);
        try {
            fclose($pipes[0]);
            stream_set_timeout($pipes[1], 10);
            $address = trim(fgets($pipes[1]));
            $this->assertMatchesRegularExpression('/\A127\.0\.0\.1:[0-9]+\z/', $address);
            config(['atlas.current_approval' => [...Peer::settings(),
                'endpoint' => 'http://'.$address.'/internal/v1/atlas/current-approval']]);
            $fixture = new DeliveryFixture('new_unit');
            $package = $fixture->package();
            $delivery = app(VerifyAtlasDelivery::class)->verify($package['hash'], DeliveryFixture::read($package['objects']));
            $expected = json_decode(DeliveryFixture::json($fixture->resolution));
            $check = app(VerifyDeliveredResolution::class);
            $result = $check->inspectCurrentApproval($delivery, $expected);
            $this->assertSame('current_at_check', $result->receipt()['status']);
            $this->assertFalse($result->receipt()['usage_allowed']);
            foreach (['not current', 'HTTP status is not accepted: 302'] as $error) {
                try {
                    $check->inspectCurrentApproval($delivery, $expected);
                    $this->fail('Expected blocked approval.');
                } catch (CatalogContractViolation $exception) {
                    $this->assertStringContainsString($error, $exception->getMessage());
                }
            }
            $this->assertSame("verified_four_requests\n", stream_get_contents($pipes[1]));
            $this->assertSame('', stream_get_contents($pipes[2]));
        } finally {
            foreach ([1, 2] as $index) {
                fclose($pipes[$index]);
            }
            if (proc_get_status($process)['running']) {
                proc_terminate($process);
            }
            proc_close($process);
        }
    }
}
