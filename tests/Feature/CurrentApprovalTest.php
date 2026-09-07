<?php

namespace Tests\Feature;

use App\Application\Catalog\CheckDeliveredResolutionApproval;
use App\Application\Contracts\AtlasDeliveryStore;
use App\Application\Contracts\CurrentApprovalClient;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use App\Infrastructure\Catalog\VerifyAtlasDelivery;
use App\Infrastructure\Catalog\VerifyDeliveredResolution;
use App\Infrastructure\Contracts\PinnedCurrentApprovalContracts;
use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Sleep;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\Support\CurrentApprovalFixture as Peer;
use Tests\Support\DeliveryFixture;
use Tests\Support\InMemoryDeliveryStore;
use Tests\TestCase;

final class CurrentApprovalTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        config(['atlas.current_approval' => Peer::settings()]);
    }

    public static function types(): array
    {
        return array_map(fn ($type) => [$type], ['alias', 'new_unit', 'new_quantity_kind', 'exact_conversion', 'context_relation', 'monetary_measure']);
    }

    #[DataProvider('types')]
    public function test_six_types_preserve_exact_evidence_and_old_base_without_granting_usage(string $type): void
    {
        Peer::accept();
        [$delivery, $expected] = $this->delivery($type);
        $observation = app(VerifyDeliveredResolution::class)->inspectCurrentApproval($delivery, $expected);
        $this->assertSame('current_at_check', $observation->receipt()['status']);
        foreach (['cache_allowed', 'automatic_mapping_allowed', 'usage_allowed', 'publish_allowed'] as $permission) {
            $this->assertFalse($observation->receipt()[$permission]);
        }
        $this->assertFalse($delivery->receipt()['current_approval_verified']);
        $this->assertSame('forensic_only', $delivery->receipt()['resolution_status']);
        $baseHash = json_decode($delivery->artifacts['resolution/payload.json'])->form->unit_catalog_sha256;
        Http::assertSent(function (Request $request) use ($expected, $baseHash, $delivery): bool {
            $query = json_decode($request->body());
            $this->assertSame(DeliveryFixture::json($expected), DeliveryFixture::json($query->expected_resolution));
            $this->assertSame($baseHash, $query->base_catalog->sha256);
            $this->assertSame($delivery->catalogs['unit:'.$baseHash]->descriptor->version, $query->base_catalog->version);
            $this->assertSame($delivery->sha256, $query->delivery_sha256);
            $this->assertSame($query->request_id, $request->header('X-Atlas-Correlation-Id')[0]);
            $this->assertSame('sha256='.hash_hmac('sha256', implode("\n", ['v1',
                $request->header('X-Atlas-Timestamp')[0], $request->header('X-Atlas-Nonce')[0],
                $query->request_id, 'POST', '/internal/v1/atlas/current-approval', hash('sha256', $request->body()),
            ]), Peer::SECRET), $request->header('X-Atlas-Signature')[0]);

            return true;
        });
        Http::assertSentCount(1);
    }

    public function test_usage_gate_requeries_and_stays_blocked_even_after_current_response(): void
    {
        Peer::accept();
        [$delivery, $expected] = $this->delivery();
        $check = app(VerifyDeliveredResolution::class);
        $check->inspectCurrentApproval($delivery, $expected);
        $this->invalid(fn () => $check->requireCurrentApproval($delivery, $expected), 'atomic finalization');
        Http::assertSentCount(2);
        $requests = Http::recorded()->pluck(0);
        $this->assertNotSame($requests[0]->header('X-Atlas-Nonce'), $requests[1]->header('X-Atlas-Nonce'));
    }

    public static function damagedResponses(): array
    {
        return array_map(fn ($damage) => [$damage], ['key_id', 'request_id', 'request_nonce', 'request_sha256', 'delivery_sha256',
            'state_sha256', 'policy', 'extra', 'reason', 'date', 'http', 'signature', 'digest', 'noncanonical', 'duplicate', 'oversize']);
    }

    #[DataProvider('damagedResponses')]
    public function test_authenticated_but_mismatched_or_malformed_responses_fail_closed(string $damage): void
    {
        Http::preventStrayRequests();
        Http::fake([Peer::URL => function (Request $request) use ($damage) {
            [$body, $status, $headers] = Peer::response($request, mutate: function (array $document) use ($damage): array {
                match ($damage) {
                    'key_id' => $document['key_id'] = 'different-key',
                    'request_id' => $document['request_id'] = '01a00000-0000-7000-8000-000000000099',
                    'request_nonce' => $document['request_nonce'] = str_repeat('b', 32),
                    'request_sha256', 'delivery_sha256', 'state_sha256' => $document[$damage] = str_repeat('0', 64),
                    'policy' => $document['policy']['usage_allowed'] = true,
                    'extra' => $document['lease'] = 'invented',
                    'reason' => $document['reason'] = 'trusted_evidence_unavailable',
                    'date' => $document['checked_at'] = 'not-a-date',
                    default => null,
                };

                return $document;
            });
            if (in_array($damage, ['noncanonical', 'duplicate', 'oversize'], true)) {
                $body = match ($damage) {
                    'noncanonical' => $body."\n", 'duplicate' => '{"key_id":"ignored",'.substr($body, 1),
                    'oversize' => str_repeat(' ', 16385),
                };
                $headers = Peer::headers($request, $body);
            }
            if ($damage === 'signature') {
                $headers['X-Atlas-Response-Signature'] = 'sha256='.str_repeat('0', 64);
            }
            if ($damage === 'digest') {
                unset($headers['X-Atlas-Response-SHA256']);
            }

            return Http::response($body, $damage === 'http' ? 409 : $status, $headers);
        }]);
        [$delivery, $expected] = $this->delivery();
        $this->invalid(fn () => app(VerifyDeliveredResolution::class)->inspectCurrentApproval($delivery, $expected));
        Http::assertSentCount(1);
    }

    public static function deniedStatuses(): array
    {
        return [[401], [403], [422], [429], [302], [500]];
    }

    #[DataProvider('deniedStatuses')]
    public function test_error_and_redirect_statuses_never_open_or_retry(int $status): void
    {
        Http::preventStrayRequests();
        Http::fake([Peer::URL => Http::response('', $status, ['Location' => 'https://other.example.test'])]);
        [$delivery, $expected] = $this->delivery();
        $this->invalid(fn () => app(VerifyDeliveredResolution::class)->inspectCurrentApproval($delivery, $expected), 'HTTP status');
        Http::assertSentCount(1);
    }

    public function test_rejection_after_a_success_is_rechecked_without_cached_authority(): void
    {
        Http::preventStrayRequests();
        $calls = 0;
        Http::fake([Peer::URL => function (Request $request) use (&$calls) {
            return Http::response(...Peer::response($request, ++$calls === 1 ? 'current' : 'not_current'));
        }]);
        [$delivery, $expected] = $this->delivery();
        $check = app(VerifyDeliveredResolution::class);
        $check->inspectCurrentApproval($delivery, $expected);
        $this->invalid(fn () => $check->inspectCurrentApproval($delivery, $expected), 'not current');
        Http::assertSentCount(2);
    }

    public function test_retry_uses_new_nonce_and_preserves_exact_request_pins(): void
    {
        Sleep::fake();
        Http::preventStrayRequests();
        $calls = 0;
        Http::fake([Peer::URL => function (Request $request) use (&$calls) {
            return Http::response(...Peer::response($request, ++$calls === 1 ? 'unavailable' : 'current'));
        }]);
        [$delivery, $expected] = $this->delivery();
        app(VerifyDeliveredResolution::class)->inspectCurrentApproval($delivery, $expected);
        Http::assertSentCount(2);
        $requests = Http::recorded()->pluck(0);
        $this->assertSame($requests[0]->body(), $requests[1]->body());
        $this->assertNotSame($requests[0]->header('X-Atlas-Nonce'), $requests[1]->header('X-Atlas-Nonce'));
    }

    public function test_previous_signed_response_cannot_be_replayed_for_a_new_query(): void
    {
        Http::preventStrayRequests();
        $reply = null;
        Http::fake([Peer::URL => function (Request $request) use (&$reply) {
            $reply ??= Peer::response($request);

            return Http::response(...$reply);
        }]);
        [$delivery, $expected] = $this->delivery();
        $check = app(VerifyDeliveredResolution::class);
        $check->inspectCurrentApproval($delivery, $expected);
        $this->invalid(fn () => $check->inspectCurrentApproval($delivery, $expected), 'authentication failed');
        Http::assertSentCount(2);
    }

    public function test_unavailability_is_bounded_and_does_not_disclose_credentials(): void
    {
        Sleep::fake();
        Http::preventStrayRequests();
        $calls = 0;
        Http::fake([Peer::URL => function (Request $request) use (&$calls) {
            $calls++;

            return (Http::failedConnection(Peer::SECRET))($request);
        }]);
        [$delivery, $expected] = $this->delivery();
        $this->invalid(fn () => app(VerifyDeliveredResolution::class)->inspectCurrentApproval($delivery, $expected), 'bounded attempts');
        $this->assertSame(2, $calls);
    }

    public function test_signed_unavailability_exhausts_bounded_attempts(): void
    {
        Sleep::fake();
        Http::preventStrayRequests();
        Http::fake([Peer::URL => fn (Request $request) => Http::response(...Peer::response($request, 'unavailable'))]);
        [$delivery, $expected] = $this->delivery();
        $this->invalid(fn () => app(VerifyDeliveredResolution::class)->inspectCurrentApproval($delivery, $expected), 'bounded attempts');
        Http::assertSentCount(2);
    }

    public static function unsafeSettings(): array
    {
        return [['enabled', false], ['endpoint', 'http://admin.example.test/internal/v1/atlas/current-approval'],
            ['endpoint', Peer::URL.'?override=1'], ['endpoint', 'https://user:pass@admin.example.test/internal/v1/atlas/current-approval'],
            ['endpoint', 'https://admin.example.test/other'], ['secret', 'short'], ['key_id', "bad\nheader"],
            ['max_attempts', 4], ['timeout_seconds', 0], ['connect_timeout_seconds', 11]];
    }

    #[DataProvider('unsafeSettings')]
    public function test_invalid_configuration_sends_nothing(string $key, mixed $value): void
    {
        Http::preventStrayRequests();
        config(['atlas.current_approval.'.$key => $value]);
        [$delivery, $expected] = $this->delivery();
        $this->invalid(fn () => app(VerifyDeliveredResolution::class)->inspectCurrentApproval($delivery, $expected));
        Http::assertNothingSent();
    }

    public function test_independent_schema_pin_detects_local_schema_replacement(): void
    {
        $directory = sys_get_temp_dir().'/atlas-approval-schema-'.bin2hex(random_bytes(8));
        mkdir($directory);
        $path = $directory.'/atlas-current-approval-request-v1.schema.json';
        file_put_contents($path, '{}');
        try {
            $this->invalid(fn () => (new PinnedCurrentApprovalContracts($directory))->validate('request', (object) []), 'schema pin');
        } finally {
            unlink($path);
            rmdir($directory);
        }
    }

    public function test_actual_entrypoint_reads_stored_bytes_each_time_and_requires_external_expected_pins(): void
    {
        Peer::accept();
        [$delivery, $expected, $package] = $this->delivery();
        $store = new InMemoryDeliveryStore;
        foreach ($package['objects'] as $path => $bytes) {
            $store->objects[$package['hash'].'/'.$path] = $bytes;
        }
        $this->app->instance(AtlasDeliveryStore::class, $store);
        $action = app(CheckDeliveredResolutionApproval::class);
        $action->inspect($delivery->sha256, $expected);
        $wrong = clone $expected;
        $wrong->decision_sha256 = str_repeat('f', 64);
        $this->invalid(fn () => $action->inspect($delivery->sha256, $wrong), 'Expected current');
        $store->objects[$package['hash'].'/manifest.json'] .= "\n";
        $this->invalid(fn () => $action->inspect($delivery->sha256, $expected));
        Http::assertSentCount(1);
        $this->assertSame([], $store->writes);
    }

    public function test_catalog_only_delivery_does_not_query_approval(): void
    {
        Http::preventStrayRequests();
        [$delivery] = $this->delivery(null);
        $this->invalid(fn () => app(VerifyDeliveredResolution::class)->inspectCurrentApproval($delivery, (object) []), 'Expected current');
        Http::assertNothingSent();
    }

    public function test_outgoing_request_is_closed_before_network_io(): void
    {
        Http::preventStrayRequests();
        [$delivery, $expected] = $this->delivery();
        $expected->actor_id = 'invented-human';
        $this->invalid(fn () => app(CurrentApprovalClient::class)->check($delivery->sha256, $expected, (object) [
            'version' => 'test', 'sha256' => str_repeat('a', 64),
        ]), 'request schema');
        Http::assertNothingSent();
    }

    public function test_cli_reports_observation_and_rechecks_before_blocking_final_usage(): void
    {
        Peer::accept();
        [$delivery, $expected, $package] = $this->delivery();
        $store = new InMemoryDeliveryStore;
        foreach ($package['objects'] as $path => $bytes) {
            $store->objects[$package['hash'].'/'.$path] = $bytes;
        }
        $this->app->instance(AtlasDeliveryStore::class, $store);
        $file = tempnam(sys_get_temp_dir(), 'atlas-expected-');
        file_put_contents($file, DeliveryFixture::json($expected));
        try {
            $this->artisan('atlas:catalog:current-approval', ['sha256' => $delivery->sha256, 'expected' => $file])
                ->expectsOutputToContain('"usage_allowed": false')->assertSuccessful();
            $this->artisan('atlas:catalog:current-approval', ['sha256' => $delivery->sha256,
                'expected' => $file, '--require-for-use' => true])
                ->expectsOutputToContain('atomic finalization')->assertFailed();
            file_put_contents($file, '{}'."\n");
            $this->artisan('atlas:catalog:current-approval', ['sha256' => $delivery->sha256, 'expected' => $file])
                ->expectsOutputToContain('exact sorted JSON')->assertFailed();
            Http::assertSentCount(2);
        } finally {
            unlink($file);
        }
    }

    public function test_schema_valid_multibyte_request_still_has_a_byte_limit(): void
    {
        Http::preventStrayRequests();
        [$delivery, $expected] = $this->delivery();
        $expected->proposal_key = str_repeat('😀', 1000);
        $expected->source->raw->asset_key = str_repeat('😀', 1024);
        $expected->source->code = str_repeat('😀', 255);
        $expected->source->dataset = str_repeat('😀', 255);
        $expected->source->release = str_repeat('😀', 255);
        $base = (object) ['version' => str_repeat('😀', 1000), 'sha256' => str_repeat('a', 64)];
        $this->invalid(fn () => app(CurrentApprovalClient::class)->check($delivery->sha256, $expected, $base), 'byte limit');
        Http::assertNothingSent();
    }

    private function delivery(?string $type = 'alias'): array
    {
        $fixture = new DeliveryFixture($type);
        $package = $fixture->package();
        $delivery = app(VerifyAtlasDelivery::class)->verify($package['hash'], DeliveryFixture::read($package['objects']));

        return [$delivery, $fixture->resolution === null ? null : json_decode(DeliveryFixture::json($fixture->resolution)), $package];
    }

    private function invalid(callable $call, string $message = ''): void
    {
        try {
            $call();
            $this->fail('Expected fail-closed approval.');
        } catch (CatalogContractViolation $exception) {
            $this->assertStringContainsString($message, $exception->getMessage());
            $this->assertStringNotContainsString(Peer::SECRET, $exception->getMessage());
        }
    }
}
