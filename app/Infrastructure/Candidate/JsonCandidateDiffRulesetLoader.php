<?php

namespace App\Infrastructure\Candidate;

use App\Application\Contracts\CandidateDiffRulesetLoader;
use App\Domain\Candidate\CandidateDiffRuleset;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use JsonException;

final readonly class JsonCandidateDiffRulesetLoader implements CandidateDiffRulesetLoader
{
    public function __construct(
        private string $path,
        private string $expectedSha256,
    ) {}

    public function load(): CandidateDiffRuleset
    {
        $contents = @file_get_contents($this->path);

        if (! is_string($contents)) {
            throw new CandidateContractViolation('Candidate diff ruleset could not be read.');
        }

        $sha256 = hash('sha256', $contents);

        if (! hash_equals($this->expectedSha256, $sha256)) {
            throw new CandidateContractViolation('Candidate diff ruleset checksum does not match its configured pin.');
        }

        try {
            $rules = json_decode($contents, true, 512, JSON_THROW_ON_ERROR);
        } catch (JsonException $exception) {
            throw new CandidateContractViolation('Candidate diff ruleset is not valid JSON.', previous: $exception);
        }

        if (! is_array($rules)) {
            throw new CandidateContractViolation('Candidate diff ruleset shape is invalid.');
        }

        $keys = array_keys($rules);
        sort($keys, SORT_STRING);

        if ($keys !== [
            'candidate_key_token',
            'comparison_schema_version',
            'domain_prefixes',
            'excluded_pointer_patterns',
            'ruleset_version',
            'schema_version',
        ]
            || ! is_string($rules['schema_version'])
            || ! is_string($rules['ruleset_version'])
            || ! is_string($rules['comparison_schema_version'])
            || ! is_string($rules['candidate_key_token'])
            || ! is_array($rules['excluded_pointer_patterns'])
            || ! is_array($rules['domain_prefixes'])
        ) {
            throw new CandidateContractViolation('Candidate diff ruleset shape is invalid.');
        }

        return new CandidateDiffRuleset(
            schemaVersion: $rules['schema_version'],
            rulesetVersion: $rules['ruleset_version'],
            comparisonSchemaVersion: $rules['comparison_schema_version'],
            sha256: $sha256,
            candidateKeyToken: $rules['candidate_key_token'],
            excludedPointerPatterns: array_values($rules['excluded_pointer_patterns']),
            domainPrefixes: array_values($rules['domain_prefixes']),
        );
    }
}
