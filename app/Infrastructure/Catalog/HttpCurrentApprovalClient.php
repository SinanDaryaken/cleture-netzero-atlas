<?php

namespace App\Infrastructure\Catalog;

use App\Application\Contracts\CurrentApprovalClient;
use App\Domain\Catalog\CurrentApprovalObservation;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use App\Domain\Catalog\SortedCatalogJson;
use App\Infrastructure\Contracts\PinnedCurrentApprovalContracts;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\Factory;
use Illuminate\Http\Client\Response;
use Illuminate\Support\Sleep;
use Illuminate\Support\Str;
use RuntimeException;
use stdClass;

final readonly class HttpCurrentApprovalClient implements CurrentApprovalClient
{
    private const PATH = '/internal/v1/atlas/current-approval';

    private const RESPONSE_SCHEMA = 'netzero-atlas-current-approval-response/v1';

    private const MAX_BYTES = 16384;

    public function __construct(
        private Factory $http,
        private SortedCatalogJson $json,
        private PinnedCurrentApprovalContracts $contracts,
        #[\SensitiveParameter] private array $settings,
    ) {}

    /** Local configuration only; never prints credentials or claims a remote grant. */
    public function connectionReadiness(): array
    {
        $problem = null;
        try {
            $this->assertConfigured();
        } catch (CatalogContractViolation $exception) {
            $problem = $exception->getMessage();
        }

        return ['enabled' => ($this->settings['enabled'] ?? false) === true,
            'endpoint_configured' => is_string($this->settings['endpoint'] ?? null) && $this->settings['endpoint'] !== '',
            'key_id_configured' => is_string($this->settings['key_id'] ?? null) && $this->settings['key_id'] !== '',
            'secret_configured' => is_string($this->settings['secret'] ?? null) && $this->settings['secret'] !== '',
            'configuration_valid' => $problem === null, 'problem' => $problem,
            'network_checked' => false, 'admin_grants_verified' => false];
    }

    public function check(string $deliverySha256, stdClass $expectedResolution, stdClass $baseCatalog): CurrentApprovalObservation
    {
        $this->assertConfigured();
        $request = (object) ['schema_version' => 'netzero-atlas-current-approval-request/v1',
            'request_id' => (string) Str::uuid7(), 'delivery_sha256' => $deliverySha256,
            'expected_resolution' => $expectedResolution, 'base_catalog' => $baseCatalog];
        $this->contracts->validate('request', $request);
        $body = $this->json->encode($request);
        if (strlen($body) > self::MAX_BYTES) {
            throw new CatalogContractViolation('Current approval request exceeds its byte limit.');
        }
        $requestHash = hash('sha256', $body);
        $stateHash = hash('sha256', $this->json->encode(['delivery_sha256' => $deliverySha256,
            'resolution' => $expectedResolution, 'base_catalog' => $baseCatalog]));
        $key = $this->settings['key_id'];
        for ($attempt = 1; $attempt <= $this->settings['max_attempts']; $attempt++) {
            if ($attempt > 1) {
                Sleep::usleep(100000 * ($attempt - 1));
            }
            $nonce = bin2hex(random_bytes(32));
            $timestamp = (string) now()->getTimestamp();
            $signature = $this->sign(['v1', $timestamp, $nonce, $request->request_id, 'POST', self::PATH, $requestHash]);
            try {
                $response = $this->http->connectTimeout($this->settings['connect_timeout_seconds'])
                    ->timeout($this->settings['timeout_seconds'])
                    ->withOptions(['allow_redirects' => false, 'verify' => true, 'cookies' => false,
                        'http_errors' => false, 'stream' => true, 'read_timeout' => $this->settings['timeout_seconds']])
                    ->withHeaders(['Accept' => 'application/json', 'Cache-Control' => 'no-store',
                        'X-Atlas-Key-Id' => $key, 'X-Atlas-Timestamp' => $timestamp, 'X-Atlas-Nonce' => $nonce,
                        'X-Atlas-Correlation-Id' => $request->request_id, 'X-Atlas-Signature' => $signature])
                    ->withBody($body, 'application/json')->post($this->settings['endpoint']);
            } catch (ConnectionException) {
                // Do not propagate HTTP exceptions containing request headers or credentials.
                continue;
            }
            $document = $this->verifyResponse($response, $request, $nonce, $requestHash, $stateHash);
            if ($document->status === 'not_current') {
                throw new CatalogContractViolation('Admin approval is not current; exact expected pins must not be updated automatically.');
            }
            if ($document->status === 'current') {
                return new CurrentApprovalObservation($deliverySha256, $request->request_id, $stateHash, $document->checked_at);
            }
        }

        throw new CatalogContractViolation('Admin current approval is unavailable after bounded attempts.');
    }

    private function verifyResponse(Response $response, stdClass $request, string $nonce, string $requestHash, string $stateHash): stdClass
    {
        $stream = $response->toPsrResponse()->getBody();
        try {
            if (! in_array($response->status(), [200, 409, 503], true)) {
                throw new CatalogContractViolation('Admin current approval HTTP status is not accepted: '.$response->status());
            }
            $bytes = '';
            $started = hrtime(true);
            while (! $stream->eof() && strlen($bytes) <= self::MAX_BYTES) {
                $chunk = $stream->read(self::MAX_BYTES + 1 - strlen($bytes));
                if ($chunk === '' && ! $stream->eof()
                    || (hrtime(true) - $started) / 1e9 > $this->settings['timeout_seconds']) {
                    throw new CatalogContractViolation('Current approval response read did not complete in time.');
                }
                $bytes .= $chunk;
            }
        } catch (CatalogContractViolation $exception) {
            throw $exception;
        } catch (RuntimeException) {
            throw new CatalogContractViolation('Current approval response read failed.');
        } finally {
            $stream->close();
        }
        if (strlen($bytes) > self::MAX_BYTES) {
            throw new CatalogContractViolation('Current approval response exceeds its byte limit.');
        }
        $responseHash = hash('sha256', $bytes);
        // Compute from OUR sent identity and exact request, before trusting any response fields.
        $signature = $this->sign([self::RESPONSE_SCHEMA, $this->settings['key_id'], $nonce, $requestHash, $responseHash]);
        if (! hash_equals($responseHash, $response->header('X-Atlas-Response-SHA256'))
            || ! hash_equals($signature, $response->header('X-Atlas-Response-Signature'))) {
            throw new CatalogContractViolation('Current approval response authentication failed.');
        }
        $document = $this->json->decode($bytes);
        $this->contracts->validate('response', $document);
        if ($document->key_id !== $this->settings['key_id'] || $document->request_nonce !== $nonce
            || $document->request_id !== $request->request_id || $document->request_sha256 !== $requestHash
            || $document->delivery_sha256 !== $request->delivery_sha256
            || $response->status() !== match ($document->status) {
                'current' => 200, 'not_current' => 409, 'unavailable' => 503
            }
            || ($document->status === 'current' && ! hash_equals($stateHash, $document->state_sha256))) {
            throw new CatalogContractViolation('Current approval response does not match the exact request and state.');
        }

        return $document;
    }

    private function sign(array $parts): string
    {
        return 'sha256='.hash_hmac('sha256', implode("\n", $parts), $this->settings['secret']);
    }

    private function assertConfigured(): void
    {
        if (($this->settings['enabled'] ?? false) !== true) {
            throw new CatalogContractViolation('Current Admin approval client is disabled; delivered approval remains forensic only.');
        }
        $endpoint = $this->settings['endpoint'] ?? null;
        $url = is_string($endpoint) ? parse_url($endpoint) : false;
        // HTTP is allowed only for a local fixture runner; remote service credentials require TLS.
        $transport = is_array($url) && (($url['scheme'] ?? '') === 'https'
            || (($url['scheme'] ?? '') === 'http' && in_array($url['host'] ?? '', ['127.0.0.1', '[::1]'], true)));
        if (! $transport || empty($url['host']) || ($url['path'] ?? '') !== self::PATH
            || isset($url['user']) || isset($url['pass']) || isset($url['query']) || isset($url['fragment'])
            || ! is_string($this->settings['key_id'] ?? null)
            || ! preg_match('/\A[\x21-\x7e]{1,255}\z/', $this->settings['key_id'])
            || ! is_string($this->settings['secret'] ?? null) || strlen($this->settings['secret']) < 32) {
            throw new CatalogContractViolation('Current approval endpoint or service credentials are not configured safely.');
        }
        foreach (['max_attempts' => 3, 'connect_timeout_seconds' => 10, 'timeout_seconds' => 30] as $name => $maximum) {
            if (! is_int($this->settings[$name] ?? null) || $this->settings[$name] < 1 || $this->settings[$name] > $maximum) {
                throw new CatalogContractViolation('Invalid bounded current approval transport setting.');
            }
        }
    }
}
