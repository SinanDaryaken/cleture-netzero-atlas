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
        public array $referencePointerPatterns = [],
        public array $mappingDomains = [],
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

        foreach ($this->referencePointerPatterns as $pattern) {
            $this->assertPointer($pattern, true);
        }

        foreach ($this->mappingDomains as $domain) {
            if (! in_array($domain, self::DOMAINS, true)) {
                throw new CandidateContractViolation('Invalid mapping diff domain.');
            }
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

    public function domainFor(string $pointer, array $record = []): string
    {
        if ($this->mappingDomains !== [] && preg_match('#^/canonical_mapping_proposals/(\d+)(?:/|$)#', $pointer, $matches)) {
            $domain = $record['canonical_mapping_proposals'][(int) $matches[1]]['domain'] ?? null;

            return $this->mappingDomains[$domain ?? '']
                ?? throw new CandidateContractViolation('Unknown mapping proposal domain in source diff.');
        }

        $match = null;

        foreach ($this->domainPrefixes as $rule) {
            $prefix = $rule['prefix'];

            if (preg_match('#^'.str_replace('\\*', '[^/]+', preg_quote($prefix, '#')).'(?:/|$)#', $pointer)
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

    public function normalizeReference(string $pointer, string $value, string $candidateKey): string
    {
        if ($this->referencePointerPatterns === []) {
            return str_replace($candidateKey, $this->candidateKeyToken, $value);
        }

        foreach ($this->referencePointerPatterns as $pattern) {
            if (preg_match('#^'.str_replace('\\*', '[^/]+', preg_quote($pattern, '#')).'$#', $pointer)) {
                if ($value === $candidateKey || str_starts_with($value, $candidateKey.':')) {
                    return $this->candidateKeyToken.substr($value, strlen($candidateKey));
                }
            }
        }

        return $value;
    }

    private function assertPointer(string $pointer, bool $allowWildcard): void
    {
        $segment = $allowWildcard ? '(?:\*|(?:[^~\/]|~0|~1)+)' : '(?:[^~\/]|~0|~1)+';

        if ($pointer === '' || preg_match('/^\/'.$segment.'(?:\/'.$segment.')*$/', $pointer) !== 1) {
            throw new CandidateContractViolation("Candidate diff ruleset contains invalid JSON Pointer {$pointer}.");
        }
    }
}
