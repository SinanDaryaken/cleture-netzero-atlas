<?php

namespace App\Infrastructure\Candidate;

use App\Application\Contracts\CandidateMappingPolicyLoader;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;

final readonly class PinnedCandidateMappingPolicy implements CandidateMappingPolicyLoader
{
    public const VERSION = 'candidate-exact-mapping-v1';

    public function __construct(private string $path, private string $sha256) {}

    public function identity(): array
    {
        $bytes = @file_get_contents($this->path);
        if (! is_string($bytes) || ! hash_equals($this->sha256, hash('sha256', $bytes))) {
            throw new CandidateContractViolation('Mapping ruleset checksum mismatch.');
        }
        $rules = json_decode($bytes, true, 512, JSON_THROW_ON_ERROR);
        $supported = ['schema_version' => '1.0.0', 'ruleset_version' => self::VERSION,
            'unit_match' => 'exact_code_or_symbol', 'geography_match' => 'exact_country_code_or_localized_name',
            'geography_role' => 'market', 'multiple_matches' => 'ambiguous', 'missing_match' => 'unresolved'];
        if ($rules != $supported) {
            throw new CandidateContractViolation('Mapping ruleset requests unsupported resolver semantics.');
        }

        return ['mapping_ruleset_version' => self::VERSION, 'mapping_ruleset_sha256' => $this->sha256];
    }
}
