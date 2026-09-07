<?php

// Standalone synthetic HTTP peer: no application bootstrap, database, or real credentials.
// A real socket exercises request headers/body and response streaming through Guzzle.
$secret = 'synthetic-current-approval-secret-not-a-real-credential';
$key = 'atlas-test-only';
$sort = function (mixed $value) use (&$sort): mixed {
    if (is_object($value)) {
        $values = get_object_vars($value);
        ksort($values, SORT_STRING);

        return (object) array_map($sort, $values);
    }
    if (is_array($value)) {
        return array_map($sort, $value);
    }

    return $value;
};
$json = fn ($value) => json_encode($sort($value), JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
$socket = stream_socket_server('tcp://127.0.0.1:0', $error, $message);
if ($socket === false) {
    exit(1);
}
echo stream_socket_get_name($socket, false).PHP_EOL;
flush();
$nonces = [];
$firstBody = null;
for ($index = 0; $index < 4; $index++) {
    $connection = stream_socket_accept($socket, 10);
    if ($connection === false) {
        exit(2);
    }
    stream_set_timeout($connection, 5);
    $requestLine = trim(fgets($connection));
    $headers = [];
    while (($line = fgets($connection)) !== false && trim($line) !== '') {
        [$name, $value] = explode(':', $line, 2);
        $headers[strtolower($name)] = trim($value);
    }
    $length = (int) ($headers['content-length'] ?? 0);
    if ($length < 1 || $length > 16384) {
        exit(3);
    }
    $body = '';
    while (strlen($body) < $length) {
        $chunk = fread($connection, $length - strlen($body));
        if ($chunk === '' || $chunk === false) {
            exit(4);
        }
        $body .= $chunk;
    }
    $query = json_decode($body, false, 64, JSON_THROW_ON_ERROR);
    $nonce = $headers['x-atlas-nonce'] ?? '';
    $requestHash = hash('sha256', $body);
    $expected = 'sha256='.hash_hmac('sha256', implode("\n", ['v1', $headers['x-atlas-timestamp'],
        $nonce, $headers['x-atlas-correlation-id'], 'POST', '/internal/v1/atlas/current-approval', $requestHash]), $secret);
    if ($requestLine !== 'POST /internal/v1/atlas/current-approval HTTP/1.1'
        || $headers['x-atlas-key-id'] !== $key || ! hash_equals($expected, $headers['x-atlas-signature'])
        || $headers['x-atlas-correlation-id'] !== $query->request_id || $json($query) !== $body
        || isset($nonces[$nonce]) || ! preg_match('/\A[a-f0-9]{64}\z/', $nonce)
        || abs(time() - (int) $headers['x-atlas-timestamp']) > 30) {
        exit(5);
    }
    $nonces[$nonce] = true;
    if ($index === 0) {
        $firstBody = $body;
    }
    if ($index === 1 && $firstBody !== $body) {
        exit(6);
    }
    // First logical check retries a signed 503. Second gets 409. Third gets redirect.
    $status = ['unavailable', 'current', 'not_current', 'redirect'][$index];
    $httpStatus = [503, 200, 409, 302][$index];
    $state = (object) ['delivery_sha256' => $query->delivery_sha256,
        'resolution' => $query->expected_resolution, 'base_catalog' => $query->base_catalog];
    $response = (object) ['schema_version' => 'netzero-atlas-current-approval-response/v1', 'key_id' => $key,
        'request_id' => $query->request_id, 'request_sha256' => $requestHash, 'request_nonce' => $nonce,
        'delivery_sha256' => $query->delivery_sha256, 'status' => $status,
        'reason' => match ($status) {
            'current' => 'exact_current_approval', 'not_current' => 'approval_or_expected_state_changed',
            default => 'trusted_evidence_unavailable',
        },
        'state_sha256' => $status === 'current' ? hash('sha256', $json($state)) : null,
        'checked_at' => gmdate('c'), 'policy' => (object) ['validity' => 'checked_at_only',
            'recheck_before_use' => true, 'cache_allowed' => false, 'automatic_mapping_allowed' => false,
            'usage_allowed' => false, 'publish_allowed' => false]];
    $bytes = $json($response);
    $hash = hash('sha256', $bytes);
    $signature = 'sha256='.hash_hmac('sha256', implode("\n", ['netzero-atlas-current-approval-response/v1',
        $key, $nonce, $requestHash, $hash]), $secret);
    fwrite($connection, "HTTP/1.1 $httpStatus Fixture\r\nContent-Type: application/json\r\nConnection: close\r\n"
        .'Content-Length: '.strlen($bytes)."\r\nX-Atlas-Response-SHA256: $hash\r\n"
        ."X-Atlas-Response-Signature: $signature\r\nLocation: http://127.0.0.1:1/never-follow\r\n\r\n".$bytes);
    fclose($connection);
}
fclose($socket);
echo "verified_four_requests\n";
