<?php

namespace Tests\Unit\Application\Candidate;

use App\Application\Candidate\SourceNormalizerRegistry;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use App\Infrastructure\Sources\Ademe\AdemeCandidateNormalizer;
use PHPUnit\Framework\TestCase;

final class SourceNormalizerRegistryTest extends TestCase
{
    public function test_resolves_a_source_normalizer_case_insensitively(): void
    {
        $normalizer = new AdemeCandidateNormalizer;
        $registry = new SourceNormalizerRegistry([$normalizer]);

        $this->assertSame($normalizer, $registry->for('ademe'));
    }

    public function test_rejects_an_unknown_source_normalizer(): void
    {
        $registry = new SourceNormalizerRegistry([]);

        $this->expectException(SourceContractViolation::class);
        $this->expectExceptionMessage('Unknown source normalizer: UNKNOWN.');

        $registry->for('UNKNOWN');
    }
}
