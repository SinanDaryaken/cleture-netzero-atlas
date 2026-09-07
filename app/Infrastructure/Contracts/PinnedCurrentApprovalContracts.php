<?php

namespace App\Infrastructure\Contracts;

use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use Opis\JsonSchema\CompliantValidator;
use Opis\JsonSchema\SchemaLoader;
use stdClass;

final readonly class PinnedCurrentApprovalContracts
{
    public const HASHES = [
        'request' => '3b69965e96762d4edae9f862732cff76b7b7d4b5bf9e095a3891b7f18a569a61',
        'response' => '13c5684160586c19988365d7c85a4b71c1a81cb80e20c6da10bc3b54aa5929b6',
    ];

    public function __construct(private string $directory) {}

    public function validate(string $name, stdClass $document): void
    {
        $pin = self::HASHES[$name] ?? throw new CatalogContractViolation('Unknown approval schema.');
        $bytes = @file_get_contents($this->directory.'/atlas-current-approval-'.$name.'-v1.schema.json');
        if (! is_string($bytes) || ! hash_equals($pin, hash('sha256', $bytes))) {
            throw new CatalogContractViolation('Independent current approval schema pin failed.');
        }
        $schema = json_decode($bytes, false, 64, JSON_THROW_ON_ERROR);
        if (! (new CompliantValidator(new SchemaLoader(resolver: null)))->validate($document, $schema)->isValid()) {
            throw new CatalogContractViolation('Closed current approval '.$name.' schema failed.');
        }
    }
}
