<?php

namespace App\Domain\Catalog;

use InvalidArgumentException;

final readonly class CatalogContractDocument
{
    public function __construct(
        public CatalogContract $contract,
        public string $version,
        public string $schemaId,
        public string $sha256,
        public string $contents,
        public string $owner,
        public string $upstreamRepository,
        public string $upstreamCommit,
        public string $upstreamGitBlob,
        public string $upstreamPath,
    ) {
        if (! preg_match('/^\d+\.\d+\.\d+$/', $this->version)
            || ! preg_match('/^[a-f0-9]{64}$/', $this->sha256)
            || ! preg_match('/^[a-f0-9]{40,64}$/', $this->upstreamCommit)
            || ! preg_match('/^[a-f0-9]{40,64}$/', $this->upstreamGitBlob)
            || $this->schemaId === ''
            || $this->owner === ''
            || $this->upstreamRepository === ''
            || $this->upstreamPath === ''
            || ! hash_equals($this->sha256, hash('sha256', $this->contents))
        ) {
            throw new InvalidArgumentException('Catalog contract integrity or provenance is invalid.');
        }
    }
}
