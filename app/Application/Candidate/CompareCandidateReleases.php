<?php

namespace App\Application\Candidate;

use App\Application\Contracts\CandidateContractRegistry;
use App\Application\Contracts\CandidateDiffRulesetLoader;
use App\Application\Contracts\CanonicalJson;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\CandidateDiffRuleset;
use App\Domain\Candidate\CandidateSourceDiff;
use App\Domain\Candidate\CanonicalCandidateEntity;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use stdClass;

final readonly class CompareCandidateReleases
{
    private const MAX_CHANGES_PER_RECORD = 512;

    public function __construct(
        private CandidateContractRegistry $contracts,
        private CandidateDiffRulesetLoader $rulesets,
        private CanonicalJson $canonicalJson,
    ) {}

    /**
     * @param  iterable<CanonicalCandidateEntity>  $current
     * @param  iterable<CanonicalCandidateEntity>  $previous
     * @return list<CandidateSourceDiff>
     */
    public function handle(iterable $current, iterable $previous = []): array
    {
        $ruleset = $this->rulesets->load();
        $schemaVersion = $this->contracts->get(CandidateContract::SourceDiffRecord)->version;
        $currentByIdentity = $this->index($current, 'current');
        $previousByIdentity = $this->index($previous, 'previous');
        $identities = array_values(array_unique([
            ...array_keys($currentByIdentity),
            ...array_keys($previousByIdentity),
        ]));
        sort($identities, SORT_STRING);
        $diffs = [];

        foreach ($identities as $identity) {
            $after = $currentByIdentity[$identity] ?? null;
            $before = $previousByIdentity[$identity] ?? null;
            $diffs[] = $this->compare($schemaVersion, $ruleset, $after, $before);
        }

        return $diffs;
    }

    private function compare(
        string $schemaVersion,
        CandidateDiffRuleset $ruleset,
        ?CanonicalCandidateEntity $after,
        ?CanonicalCandidateEntity $before,
    ): CandidateSourceDiff {
        $entity = $after ?? $before;

        if ($entity === null) {
            throw new CandidateContractViolation('Candidate source diff requires at least one entity.');
        }

        $afterProjection = $after === null ? null : $this->projection($after, $ruleset);
        $beforeProjection = $before === null ? null : $this->projection($before, $ruleset);
        $afterSha256 = $afterProjection === null ? null : hash('sha256', $this->canonicalJson->encode($afterProjection));
        $beforeSha256 = $beforeProjection === null ? null : hash('sha256', $this->canonicalJson->encode($beforeProjection));
        [$classification, $changes] = $this->classificationAndChanges(
            $ruleset,
            $after,
            $before,
            $afterProjection,
            $beforeProjection,
            $afterSha256,
            $beforeSha256,
        );
        $identity = [
            'logical_key' => $entity->record['logical_key'],
            'variant_key' => $entity->record['variant_key'],
            'candidate_key' => $after?->candidateKey,
            'previous_candidate_key' => $before?->candidateKey,
            'before_comparison_sha256' => $beforeSha256,
            'after_comparison_sha256' => $afterSha256,
            'comparison_schema_version' => $ruleset->comparisonSchemaVersion,
            'diff_ruleset_version' => $ruleset->rulesetVersion,
        ];

        return new CandidateSourceDiff(
            schemaVersion: $schemaVersion,
            diffKey: 'diff:'.hash('sha256', $this->canonicalJson->encode($identity)),
            logicalKey: $identity['logical_key'],
            variantKey: $identity['variant_key'],
            candidateKey: $after?->candidateKey,
            previousCandidateKey: $before?->candidateKey,
            classification: $classification,
            beforeComparisonSha256: $beforeSha256,
            afterComparisonSha256: $afterSha256,
            comparisonSchemaVersion: $ruleset->comparisonSchemaVersion,
            diffRulesetVersion: $ruleset->rulesetVersion,
            changes: $changes,
        );
    }

    /**
     * @param  array<string, scalar|null>|null  $afterProjection
     * @param  array<string, scalar|null>|null  $beforeProjection
     * @return array{string, list<array<string, mixed>>}
     */
    private function classificationAndChanges(
        CandidateDiffRuleset $ruleset,
        ?CanonicalCandidateEntity $after,
        ?CanonicalCandidateEntity $before,
        ?array $afterProjection,
        ?array $beforeProjection,
        ?string $afterSha256,
        ?string $beforeSha256,
    ): array {
        if ($before === null && $after !== null) {
            return ['added', [$this->boundaryChange('add', $after, null)]];
        }

        if ($after === null && $before !== null) {
            return ['removed', [$this->boundaryChange('remove', null, $before)]];
        }

        if ($after === null || $before === null || $afterProjection === null || $beforeProjection === null) {
            throw new CandidateContractViolation('Candidate source diff state is inconsistent.');
        }

        if ($afterSha256 === $beforeSha256) {
            return ['unchanged', []];
        }

        $pointers = array_values(array_unique([
            ...array_keys($afterProjection),
            ...array_keys($beforeProjection),
        ]));
        sort($pointers, SORT_STRING);
        $changes = [];

        foreach ($pointers as $pointer) {
            $hasAfter = array_key_exists($pointer, $afterProjection);
            $hasBefore = array_key_exists($pointer, $beforeProjection);

            if ($hasAfter && $hasBefore && $afterProjection[$pointer] === $beforeProjection[$pointer]) {
                continue;
            }

            $operation = $hasAfter && $hasBefore ? 'replace' : ($hasAfter ? 'add' : 'remove');
            $changes[] = [
                'json_pointer' => $pointer,
                'domain' => $ruleset->domainFor($pointer),
                'operation' => $operation,
                'before' => $hasBefore
                    ? ['presence' => 'present', 'value' => $beforeProjection[$pointer]]
                    : ['presence' => 'absent'],
                'after' => $hasAfter
                    ? ['presence' => 'present', 'value' => $afterProjection[$pointer]]
                    : ['presence' => 'absent'],
                'provenance_refs' => $this->provenanceRefs($hasAfter ? $after : $before),
            ];

            if (count($changes) > self::MAX_CHANGES_PER_RECORD) {
                throw new CandidateContractViolation('Candidate source diff exceeds the contract change limit.');
            }
        }

        return ['changed', $changes];
    }

    /** @return array<string, scalar|null> */
    private function projection(CanonicalCandidateEntity $entity, CandidateDiffRuleset $ruleset): array
    {
        $projection = [];

        foreach ($entity->record as $key => $value) {
            $pointer = '/'.$this->escapePointer((string) $key);

            if (! $ruleset->excludes($pointer)) {
                $this->flatten($value, $pointer, $projection, $entity->candidateKey, $ruleset);
            }
        }

        ksort($projection, SORT_STRING);

        foreach (array_keys($projection) as $pointer) {
            $ruleset->domainFor($pointer);
        }

        return $projection;
    }

    /** @param array<string, scalar|null> $projection */
    private function flatten(
        mixed $value,
        string $pointer,
        array &$projection,
        string $candidateKey,
        CandidateDiffRuleset $ruleset,
    ): void {
        if ($ruleset->excludes($pointer)) {
            return;
        }

        if ($value instanceof stdClass) {
            $value = get_object_vars($value);
        }

        if (is_array($value)) {
            foreach ($value as $key => $child) {
                $this->flatten(
                    $child,
                    $pointer.'/'.$this->escapePointer((string) $key),
                    $projection,
                    $candidateKey,
                    $ruleset,
                );
            }

            return;
        }

        if (is_float($value) || (! is_scalar($value) && $value !== null)) {
            throw new CandidateContractViolation("Candidate comparison value at {$pointer} is not an allowed scalar.");
        }

        $projection[$pointer] = is_string($value)
            ? str_replace($candidateKey, $ruleset->candidateKeyToken, $value)
            : $value;
    }

    /** @return array<string, CanonicalCandidateEntity> */
    private function index(iterable $entities, string $side): array
    {
        $indexed = [];

        foreach ($entities as $entity) {
            if (! $entity instanceof CanonicalCandidateEntity) {
                throw new CandidateContractViolation("Candidate source diff {$side} input is invalid.");
            }

            $logicalKey = $entity->record['logical_key'] ?? null;
            $variantKey = $entity->record['variant_key'] ?? null;

            if (! is_string($logicalKey) || ! is_string($variantKey)) {
                throw new CandidateContractViolation("Candidate source diff {$side} identity is invalid.");
            }

            $identity = $logicalKey."\0".$variantKey;

            if (isset($indexed[$identity])) {
                throw new CandidateContractViolation("Candidate source diff {$side} input contains a duplicate identity.");
            }

            $indexed[$identity] = $entity;
        }

        return $indexed;
    }

    /** @return array<string, mixed> */
    private function boundaryChange(
        string $operation,
        ?CanonicalCandidateEntity $after,
        ?CanonicalCandidateEntity $before,
    ): array {
        $entity = $after ?? $before;

        if ($entity === null) {
            throw new CandidateContractViolation('Candidate boundary diff has no entity.');
        }

        return [
            'json_pointer' => '/record_sha256',
            'domain' => 'identity',
            'operation' => $operation,
            'before' => $before === null
                ? ['presence' => 'absent']
                : ['presence' => 'present', 'value' => $before->recordSha256],
            'after' => $after === null
                ? ['presence' => 'absent']
                : ['presence' => 'present', 'value' => $after->recordSha256],
            'provenance_refs' => $this->provenanceRefs($entity),
        ];
    }

    /** @return non-empty-list<string> */
    private function provenanceRefs(CanonicalCandidateEntity $entity): array
    {
        foreach ($entity->record['provenance'] ?? [] as $provenance) {
            $key = is_array($provenance) ? ($provenance['provenance_key'] ?? null) : null;

            if (is_string($key) && $key !== '') {
                return [$key];
            }
        }

        throw new CandidateContractViolation("Candidate {$entity->candidateKey} has no usable provenance reference.");
    }

    private function escapePointer(string $segment): string
    {
        return str_replace(['~', '/'], ['~0', '~1'], $segment);
    }
}
