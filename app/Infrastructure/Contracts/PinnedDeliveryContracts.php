<?php

namespace App\Infrastructure\Contracts;

use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use Opis\JsonSchema\CompliantValidator;
use Opis\JsonSchema\Errors\ErrorFormatter;
use Opis\JsonSchema\SchemaLoader;

final class PinnedDeliveryContracts
{
    public const ROOTS = [
        'atlas-delivery-contract-v1.manifest.json' => '6b9158b322ae825034c2e6ccaf4b3a6d79697321e7e1390947df0dea0cb71146',
        'atlas-catalog-contract-v2.1.manifest.json' => '70c816e4d765f76c543b7685ee70d7306ec159030a6133cadc57ccbefcf4fbe9',
        'factor-context-contract-v1.manifest.json' => 'ba188dd46b11515daba809959d42f715458168e63aaa400390d9e59e70fb629c',
        'review-catalog-contract-v1.manifest.json' => '08c03d3eda2eb120c066ef7db2be6dbd9a7930f17272839d548758aae2e607cb',
        'source-proposal-contract-v1.manifest.json' => '5bfc20acc6c5a2779499816cb50597c22e997191ea08e0f612a0c5a9e9e24dce',
    ];

    public function __construct(private readonly string $directory) {}

    /** @param list<string> $roots @return array<string, string> */
    public function files(array $roots): array
    {
        $queue = [];
        foreach ($roots as $root) {
            $queue[] = ['path' => $root, 'sha256' => self::ROOTS[$root] ?? throw new CatalogContractViolation('Untrusted contract root.')];
        }
        $files = [];
        while ($queue !== []) {
            $pin = array_shift($queue);
            $name = $pin['path'];
            if (! preg_match('/\A[a-z0-9][a-z0-9.-]*\.json\z/', $name)) {
                throw new CatalogContractViolation('Unsafe contract path.');
            }
            $bytes = $files[$name] ?? @file_get_contents($this->directory.'/'.$name);
            if (! is_string($bytes) || ! hash_equals($pin['sha256'], hash('sha256', $bytes))) {
                throw new CatalogContractViolation('Independent contract pin failed: '.$name);
            }
            $document = json_decode($bytes, false, 64, JSON_THROW_ON_ERROR);
            if (isset($pin['schema_id']) && ($document->{'$id'} ?? null) !== $pin['schema_id']) {
                throw new CatalogContractViolation('Contract schema ID mismatch.');
            }
            if (isset($files[$name])) {
                continue;
            }
            $files[$name] = $bytes;
            if (str_ends_with($name, '.manifest.json')) {
                if (($document->owner_repository ?? null) !== 'cleture-netzero-admin') {
                    throw new CatalogContractViolation('Invalid contract owner.');
                }
                foreach ([...($document->contracts ?? []), ...($document->imports ?? []), ...(isset($document->registry) ? [$document->registry] : [])] as $child) {
                    $queue[] = (array) $child;
                }
            }
        }

        return $files;
    }

    public function validate(string $schemaFile, object $value): void
    {
        $files = $this->files(array_keys(self::ROOTS));
        $schema = json_decode($files[$schemaFile] ?? throw new CatalogContractViolation('Unknown schema.'), false, 64, JSON_THROW_ON_ERROR);
        $result = (new CompliantValidator(new SchemaLoader(resolver: null)))->validate($value, $schema);
        if (! $result->isValid()) {
            $detail = (new ErrorFormatter)->format($result->error());
            throw new CatalogContractViolation($schemaFile.' validation failed: '.json_encode($detail));
        }
    }
}
