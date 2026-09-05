<?php

namespace App\Domain\Candidate;

final class CandidateRecordReferences
{
    public function inspect(array $record): array
    {
        $issues = [];
        $sets = [];
        foreach (['components' => 'component_key', 'evidence' => 'evidence_key', 'provenance' => 'provenance_key', 'canonical_mapping_proposals' => 'proposal_key', 'geography_proposals' => 'proposal_key', 'reporting_applicability_proposals' => 'proposal_key'] as $field => $key) {
            foreach ($record[$field] as $index => $item) {
                if (isset($sets[$key][$item[$key]])) {
                    $issues[] = "/{$field}/{$index}/{$key}";
                }
                $sets[$key][$item[$key]] = $item;
            }
        }
        if (! isset($sets['component_key'][$record['primary_component_key']])) {
            $issues[] = '/primary_component_key';
        }
        foreach ($record['components'] as $index => $component) {
            if ($component['methodology_ref'] !== $record['methodology']['methodology_key']) {
                $issues[] = "/components/{$index}/methodology_ref";
            }
        }
        if ($record['relationships'] !== []) {
            $issues[] = '/relationships';
        }
        $this->walk($record, '', $sets, $issues);

        return array_values(array_unique($issues));
    }

    private function walk(array $node, string $pointer, array $sets, array &$issues): void
    {
        foreach ($node as $key => $value) {
            $path = $pointer.'/'.str_replace(['~', '/'], ['~0', '~1'], (string) $key);
            if (in_array($key, ['provenance_refs', 'evidence_refs'], true)) {
                $set = $key === 'provenance_refs' ? 'provenance_key' : 'evidence_key';
                foreach ($value as $index => $ref) {
                    if (! isset($sets[$set][$ref])) {
                        $issues[] = $path.'/'.$index;
                    }
                }
            } elseif ($key === 'mapping_proposal_key') {
                if ($value === null || ($sets['proposal_key'][$value]['domain'] ?? null) !== 'unit') {
                    $issues[] = $path;
                }
            } elseif (is_array($value)) {
                $this->walk($value, $path, $sets, $issues);
            }
        }
    }

    public function pointerExists(array $record, string $pointer): bool
    {
        if ($pointer === '') {
            return true;
        }
        $value = $record;
        foreach (explode('/', substr($pointer, 1)) as $segment) {
            $key = str_replace(['~1', '~0'], ['/', '~'], $segment);
            if (is_object($value)) {
                $value = get_object_vars($value);
            }
            if (! is_array($value) || ! array_key_exists($key, $value)) {
                return false;
            }
            $value = $value[$key];
        }

        return true;
    }
}
