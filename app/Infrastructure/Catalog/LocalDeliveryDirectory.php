<?php

namespace App\Infrastructure\Catalog;

use App\Domain\Catalog\Exceptions\CatalogContractViolation;

final readonly class LocalDeliveryDirectory
{
    public function __construct(private string $directory) {}

    public function read(string $path, int $limit): string
    {
        $root = realpath($this->directory);
        if ($root === false || ! preg_match('#\A(?:manifest\.json|objects/sha256/[a-f0-9]{64})\z#', $path)) {
            throw new CatalogContractViolation('Invalid delivery directory or path.');
        }
        $file = $root.'/'.$path;
        $resolved = realpath($file);
        $cursor = $root;
        foreach (explode('/', $path) as $part) {
            $cursor .= '/'.$part;
            if (is_link($cursor)) {
                throw new CatalogContractViolation('Delivery symlinks are forbidden.');
            }
        }
        if ($resolved === false || ! str_starts_with($resolved, $root.'/') || ! is_file($file)) {
            throw new CatalogContractViolation('Missing or escaping delivery artifact.');
        }
        $stream = fopen($file, 'rb');
        if ($stream === false) {
            throw new CatalogContractViolation('Delivery artifact cannot be opened.');
        }
        try {
            $bytes = stream_get_contents($stream, $limit + 1);
        } finally {
            fclose($stream);
        }
        if ($bytes === false || strlen($bytes) > $limit) {
            throw new CatalogContractViolation('Delivery artifact exceeds its byte bound.');
        }

        return $bytes;
    }
}
