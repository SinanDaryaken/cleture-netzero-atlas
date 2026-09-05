<?php

namespace App\Domain\Candidate;

use App\Domain\Candidate\Exceptions\CandidateContractViolation;

final readonly class CandidateValidationRuleset
{
    public const RULE_CODES = ['reference_invalid', 'provenance_invalid', 'provenance_coarse', 'mapping_invalid', 'mapping_unresolved', 'mapping_unverifiable', 'dimension_unverified', 'temporal_invalid', 'temporal_unknown', 'primary_value_missing', 'primary_component_mismatch', 'negative_value_review', 'formula_unverified'];

    public function __construct(public array $document, public string $sha256)
    {
        $keys = array_keys($document);
        sort($keys);
        if ($keys !== ['required_geography_roles', 'required_mapping_domains', 'rules', 'ruleset_version', 'schema_version']
            || $document['schema_version'] !== '1.0.0' || ! is_string($document['ruleset_version']) || $document['ruleset_version'] === ''
            || preg_match('/^[a-f0-9]{64}$/', $sha256) !== 1 || ! is_array($document['rules'])) {
            throw new CandidateContractViolation('Invalid validation ruleset identity or shape.');
        }
        $codes = array_keys($document['rules']);
        $expected = self::RULE_CODES;
        sort($codes);
        sort($expected);
        if ($codes !== $expected) {
            throw new CandidateContractViolation('Validation ruleset must configure every supported rule exactly once.');
        }
        foreach ($document['rules'] as $rule) {
            $keys = is_array($rule) ? array_keys($rule) : [];
            sort($keys);
            if ($keys !== ['message', 'package_block', 'severity'] || ! is_bool($rule['package_block'])
                || ! in_array($rule['severity'], ['warning', 'review', 'blocking'], true)
                || ! is_string($rule['message']) || $rule['message'] === '') {
                throw new CandidateContractViolation('Invalid validation rule policy.');
            }
        }
        // Integrity invariants cannot be downgraded by business policy.
        foreach (['reference_invalid', 'provenance_invalid', 'mapping_invalid', 'primary_component_mismatch'] as $code) {
            if ($document['rules'][$code]['package_block'] !== true || $document['rules'][$code]['severity'] !== 'blocking') {
                throw new CandidateContractViolation('Validation ruleset cannot disable integrity gates.');
            }
        }
        foreach (['required_mapping_domains' => ['unit', 'taxonomy', 'intended_use', 'source', 'dataset', 'material', 'logical_factor', 'methodology'], 'required_geography_roles' => ['market', 'origin', 'calculation_applicability']] as $key => $allowed) {
            $values = $document[$key];
            if (! is_array($values) || ! array_is_list($values) || $values === [] || count($values) !== count(array_unique($values)) || array_diff($values, $allowed) !== []) {
                throw new CandidateContractViolation('Invalid required mapping policy.');
            }
        }
    }

    public function finding(string $code, string $candidateKey, string $pointer, array $evidenceRefs = [], array $context = []): CandidateFinding
    {
        $rule = $this->document['rules'][$code] ?? throw new CandidateContractViolation('Unknown validation rule.');

        return new CandidateFinding($code, $rule['severity'], $candidateKey, $rule['message'], $pointer, $evidenceRefs, $context);
    }
}
