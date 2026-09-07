<?php

namespace Tests\Support;

use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;

/** Synthetic wire peer; independent serialization, no production signing helpers. */
final class CurrentApprovalFixture
{
    public const KEY = 'atlas-test-only';

    public const SECRET = 'synthetic-current-approval-secret-not-a-real-credential';

    public const URL = 'https://admin.example.test/internal/v1/atlas/current-approval';

    public static function settings(): array
    {
        return ['enabled' => true, 'endpoint' => self::URL, 'key_id' => self::KEY, 'secret' => self::SECRET,
            'max_attempts' => 2, 'connect_timeout_seconds' => 1, 'timeout_seconds' => 2];
    }

    public static function response(Request $request, string $status = 'current', ?callable $mutate = null): array
    {
        $query = json_decode($request->body());
        $document = ['schema_version' => 'netzero-atlas-current-approval-response/v1', 'key_id' => self::KEY,
            'request_id' => $query->request_id, 'request_sha256' => hash('sha256', $request->body()),
            'request_nonce' => $request->header('X-Atlas-Nonce')[0], 'delivery_sha256' => $query->delivery_sha256,
            'status' => $status, 'reason' => match ($status) {
                'current' => 'exact_current_approval', 'not_current' => 'approval_or_expected_state_changed',
                'unavailable' => 'trusted_evidence_unavailable',
            },
            'state_sha256' => $status === 'current' ? hash('sha256', DeliveryFixture::json([
                'delivery_sha256' => $query->delivery_sha256, 'resolution' => $query->expected_resolution, 'base_catalog' => $query->base_catalog,
            ])) : null,
            'checked_at' => '2026-09-07T12:00:00+00:00',
            'policy' => ['validity' => 'checked_at_only', 'recheck_before_use' => true, 'cache_allowed' => false,
                'automatic_mapping_allowed' => false, 'usage_allowed' => false, 'publish_allowed' => false]];
        if ($mutate !== null) {
            $document = $mutate($document);
        }
        $body = DeliveryFixture::json($document);

        return [$body, match ($status) {
            'current' => 200, 'not_current' => 409, 'unavailable' => 503
        }, self::headers($request, $body)];
    }

    public static function headers(Request $request, string $body): array
    {
        $hash = hash('sha256', $body);

        return ['Content-Type' => 'application/json', 'Cache-Control' => 'no-store, private',
            'X-Atlas-Response-SHA256' => $hash,
            'X-Atlas-Response-Signature' => 'sha256='.hash_hmac('sha256', implode("\n", [
                'netzero-atlas-current-approval-response/v1', self::KEY, $request->header('X-Atlas-Nonce')[0],
                hash('sha256', $request->body()), $hash,
            ]), self::SECRET)];
    }

    public static function accept(): void
    {
        Http::preventStrayRequests();
        Http::fake([self::URL => fn (Request $request) => Http::response(...self::response($request))]);
    }
}
