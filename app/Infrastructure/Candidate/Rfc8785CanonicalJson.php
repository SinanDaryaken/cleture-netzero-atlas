<?php

namespace App\Infrastructure\Candidate;

use App\Application\Contracts\CanonicalJson;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use JsonException;
use stdClass;

final class Rfc8785CanonicalJson implements CanonicalJson
{
    private const MAX_SAFE_INTEGER = 9007199254740991;

    public function encode(mixed $value): string
    {
        return match (true) {
            $value === null => 'null',
            is_bool($value) => $value ? 'true' : 'false',
            is_int($value) => $this->integer($value),
            is_float($value) => throw new CandidateContractViolation(
                'Binary floating-point values are forbidden in candidate canonical JSON.',
            ),
            is_string($value) => $this->string($value),
            $value instanceof stdClass => $this->object(get_object_vars($value)),
            is_array($value) && array_is_list($value) => $this->list($value),
            is_array($value) => $this->object($value),
            default => throw new CandidateContractViolation('Candidate canonical JSON contains an unsupported value.'),
        };
    }

    private function integer(int $value): string
    {
        if ($value < -self::MAX_SAFE_INTEGER || $value > self::MAX_SAFE_INTEGER) {
            throw new CandidateContractViolation('Candidate canonical JSON integer exceeds the I-JSON safe range.');
        }

        return (string) $value;
    }

    private function string(string $value): string
    {
        if (! mb_check_encoding($value, 'UTF-8')) {
            throw new CandidateContractViolation('Candidate canonical JSON contains invalid UTF-8.');
        }

        try {
            return json_encode(
                $value,
                JSON_THROW_ON_ERROR
                    | JSON_UNESCAPED_LINE_TERMINATORS
                    | JSON_UNESCAPED_SLASHES
                    | JSON_UNESCAPED_UNICODE,
            );
        } catch (JsonException $exception) {
            throw new CandidateContractViolation('Candidate canonical JSON string could not be encoded.', previous: $exception);
        }
    }

    /** @param list<mixed> $values */
    private function list(array $values): string
    {
        return '['.implode(',', array_map($this->encode(...), $values)).']';
    }

    /** @param array<array-key, mixed> $values */
    private function object(array $values): string
    {
        $members = [];

        foreach ($values as $key => $value) {
            if (! is_string($key)) {
                throw new CandidateContractViolation('Candidate canonical JSON object keys must be strings.');
            }

            $members[$key] = $value;
        }

        uksort($members, $this->compareUtf16(...));
        $encoded = [];

        foreach ($members as $key => $value) {
            $encoded[] = $this->string($key).':'.$this->encode($value);
        }

        return '{'.implode(',', $encoded).'}';
    }

    private function compareUtf16(string $left, string $right): int
    {
        return strcmp(
            mb_convert_encoding($left, 'UTF-16BE', 'UTF-8'),
            mb_convert_encoding($right, 'UTF-16BE', 'UTF-8'),
        );
    }
}
