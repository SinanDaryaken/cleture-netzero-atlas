<?php

namespace Tests\Unit\Infrastructure\Candidate;

use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Infrastructure\Candidate\Rfc8785CanonicalJson;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

final class Rfc8785CanonicalJsonTest extends TestCase
{
    public function test_orders_object_members_by_utf16_code_units_and_uses_minimal_json(): void
    {
        $value = [
            "\u{E000}" => 1,
            'z' => null,
            '😀' => 2,
            'a' => "slash/quote\"\n",
        ];

        $encoded = (new Rfc8785CanonicalJson)->encode($value);

        $this->assertSame("{\"a\":\"slash/quote\\\"\\n\",\"z\":null,\"😀\":2,\"\u{E000}\":1}", $encoded);
    }

    public function test_preserves_list_order_and_distinguishes_an_empty_object(): void
    {
        $value = ['items' => [true, false, null], 'extensions' => (object) []];

        $encoded = (new Rfc8785CanonicalJson)->encode($value);

        $this->assertSame('{"extensions":{},"items":[true,false,null]}', $encoded);
    }

    /** @return array<string, array{mixed, string}> */
    public static function unsupportedValues(): array
    {
        return [
            'binary float' => [0.1, 'Binary floating-point values are forbidden'],
            'unsafe integer' => [9007199254740992, 'integer exceeds the I-JSON safe range'],
        ];
    }

    #[DataProvider('unsupportedValues')]
    public function test_rejects_values_that_cannot_be_canonicalized_safely(mixed $value, string $message): void
    {
        $this->expectException(CandidateContractViolation::class);
        $this->expectExceptionMessage($message);

        (new Rfc8785CanonicalJson)->encode($value);
    }
}
