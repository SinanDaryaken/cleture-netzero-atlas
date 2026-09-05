<?php

namespace App\Domain\Candidate;

use App\Domain\Candidate\Exceptions\CandidateContractViolation;

final readonly class CandidateDiffRuleset
{
    private const DOMAINS = [
        'identity',
        'value',
        'unit',
        'geography',
        'temporal',
        'methodology',
        'license',
        'taxonomy',
        'applicability',
        'quality',
        'provenance',
        'extension',
    ];

    /**
     * @param  list<string>  $excludedPointerPatterns
     * @param  list<array{prefix: string, domain: string}>  $domainPrefixes
     */
    public function __construct(
        public string $schemaVersion,
        public string $rulesetVersion,
        public string $comparisonSchemaVersion,
        public string $sha256,
        public string $candidateKeyToken,
        public array $excludedPointerPatterns,
        public array $domainPrefixes,
    ) {
        if ($this->schemaVersion === '' || $this->rulesetVersion === '' || $this->comparisonSchemaVersion === '') {
            throw new CandidateContractViolation('Candidate diff ruleset identity cannot be empty.');
        }

        if (preg_match('/^[a-f0-9]{64}$/', $this->sha256) !== 1
            || $this->candidateKeyToken === ''
            || $this->domainPrefixes === []
        ) {
            throw new CandidateContractViolation('Candidate diff ruleset integrity is invalid.');
        }

        $knownPrefixes = [];

        foreach ($this->excludedPointerPatterns as $pattern) {
            $this->assertPointer($pattern, true);
        }

        foreach ($this->domainPrefixes as $rule) {
            $prefix = $rule['prefix'] ?? null;
            $domain = $rule['domain'] ?? null;

            if (! is_string($prefix) || ! is_string($domain) || isset($knownPrefixes[$prefix])) {
                throw new CandidateContractViolation('Candidate diff ruleset contains an invalid or duplicate prefix.');
            }

            $this->assertPointer($prefix, false);

            if (! in_array($domain, self::DOMAINS, true)) {
                throw new CandidateContractViolation("Candidate diff ruleset contains unsupported domain {$domain}.");
            }

            $knownPrefixes[$prefix] = true;
        }
    }

    public function excludes(string $pointer): bool
    {
        $segments = explode('/', ltrim($pointer, '/'));

        foreach ($this->excludedPointerPatterns as $pattern) {
            $patternSegments = explode('/', ltrim($pattern, '/'));

            if (count($segments) !== count($patternSegments)) {
                continue;
            }

            foreach ($patternSegments as $index => $patternSegment) {
                if ($patternSegment !== '*' && $patternSegment !== $segments[$index]) {
                    continue 2;
                }
            }

            return true;
        }

        return false;
    }

    public function domainFor(string $pointer): string
    {
        $match = null;

        foreach ($this->domainPrefixes as $rule) {
            $prefix = $rule['prefix'];

            if (($pointer === $prefix || str_starts_with($pointer, $prefix.'/'))
                && ($match === null || strlen($prefix) > strlen($match['prefix']))
            ) {
                $match = $rule;
            }
        }

        if ($match === null) {
            throw new CandidateContractViolation("Candidate diff ruleset has no domain for {$pointer}.");
        }

        return $match['domain'];
    }

    private function assertPointer(string $pointer, bool $allowWildcard): void
    {
        $segment = $allowWildcard ? '(?:\*|(?:[^~\/]|~0|~1)+)' : '(?:[^~\/]|~0|~1)+';

        if ($pointer === '' || preg_match('/^\/'.$segment.'(?:\/'.$segment.')*$/', $pointer) !== 1) {
            throw new CandidateContractViolation("Candidate diff ruleset contains invalid JSON Pointer {$pointer}.");
        }
    }
}
