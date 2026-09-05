<?php

namespace App\Infrastructure\Candidate;

use App\Application\Contracts\CandidateValidationRulesetLoader;
use App\Domain\Candidate\CandidateValidationRuleset;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;

final readonly class JsonCandidateValidationRulesetLoader implements CandidateValidationRulesetLoader
{
    public function __construct(private string $path, private string $expectedSha256) {}

    public function load(): CandidateValidationRuleset
    {
        $bytes = @file_get_contents($this->path);
        if (! is_string($bytes) || ! hash_equals($this->expectedSha256, hash('sha256', $bytes))) {
            throw new CandidateContractViolation('Validation ruleset bytes do not match the configured pin.');
        }
        try {
            $document = json_decode($bytes, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $exception) {
            throw new CandidateContractViolation('Invalid validation ruleset JSON.', previous: $exception);
        }
        if (! is_array($document)) {
            throw new CandidateContractViolation('Validation ruleset must be an object.');
        }

        return new CandidateValidationRuleset($document, $this->expectedSha256);
    }
}
