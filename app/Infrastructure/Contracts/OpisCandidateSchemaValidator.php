<?php

namespace App\Infrastructure\Contracts;

use App\Application\Contracts\CandidateContractRegistry;
use App\Application\Contracts\CandidateSchemaValidator;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use JsonException;
use Opis\JsonSchema\CompliantValidator;
use Opis\JsonSchema\Errors\ErrorFormatter;
use Opis\JsonSchema\SchemaLoader;

final class OpisCandidateSchemaValidator implements CandidateSchemaValidator
{
    private CompliantValidator $validator;

    /** @var array<string, object> */
    private array $schemas = [];

    public function __construct(private readonly CandidateContractRegistry $contracts)
    {
        $this->validator = new CompliantValidator(
            new SchemaLoader(resolver: null),
            max_errors: 100,
            stop_at_first_error: false,
        );
    }

    public function assertValid(CandidateContract $contract, array $record): void
    {
        try {
            $instance = json_decode(
                json_encode($record, JSON_THROW_ON_ERROR),
                false,
                512,
                JSON_THROW_ON_ERROR,
            );
        } catch (JsonException $exception) {
            throw new CandidateContractViolation('Candidate record could not be converted to a JSON object.', previous: $exception);
        }

        $result = $this->validator->validate($instance, $this->schema($contract));

        if ($result->isValid()) {
            return;
        }

        $error = $result->error();

        if ($error === null) {
            throw new CandidateContractViolation("Candidate {$contract->value} failed JSON Schema validation.");
        }

        $formatted = (new ErrorFormatter)->formatOutput($error, 'basic');
        $details = array_map(
            static fn (array $item): string => sprintf(
                '%s: %s',
                ltrim((string) ($item['instanceLocation'] ?? ''), '#') ?: '/',
                (string) ($item['error'] ?? 'JSON Schema validation failed.'),
            ),
            array_slice($formatted['errors'] ?? [], 0, 10),
        );

        throw new CandidateContractViolation(
            "Candidate {$contract->value} failed JSON Schema validation: ".implode('; ', $details),
        );
    }

    private function schema(CandidateContract $contract): object
    {
        if (isset($this->schemas[$contract->value])) {
            return $this->schemas[$contract->value];
        }

        $document = $this->contracts->get($contract);

        try {
            $schema = json_decode($document->contents, false, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new CandidateContractViolation(
                "Pinned candidate {$contract->value} schema is not valid JSON.",
                previous: $exception,
            );
        }

        if (! is_object($schema)) {
            throw new CandidateContractViolation("Pinned candidate {$contract->value} schema must be a JSON object.");
        }

        $this->assertOnlyLocalReferences($schema);

        return $this->schemas[$contract->value] = $schema;
    }

    private function assertOnlyLocalReferences(mixed $value): void
    {
        if (is_object($value)) {
            foreach (get_object_vars($value) as $key => $child) {
                if ($key === '$ref' && (! is_string($child) || ! str_starts_with($child, '#/'))) {
                    throw new CandidateContractViolation('Candidate schemas may only contain local JSON Pointer references.');
                }

                $this->assertOnlyLocalReferences($child);
            }

            return;
        }

        if (is_array($value)) {
            foreach ($value as $child) {
                $this->assertOnlyLocalReferences($child);
            }
        }
    }
}
