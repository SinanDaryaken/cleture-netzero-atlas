<?php

namespace App\Domain\Catalog;

use App\Domain\Catalog\Exceptions\CatalogContractViolation;

final class ReviewCatalogLookup
{
    public function lookup(CatalogSnapshot $snapshot, string $canonicalId): array
    {
        $catalog = $snapshot->descriptor->catalog;
        if (! in_array($catalog, [CatalogType::Taxonomy, CatalogType::IntendedUse], true)) {
            throw new CatalogContractViolation('A review catalog is required.');
        }
        $entries = array_column($snapshot->payload[$catalog === CatalogType::Taxonomy ? 'nodes' : 'uses'], null, 'canonical_id');
        $entry = $entries[$canonicalId] ?? null;
        $status = $entry === null ? 'unresolved' : ($this->active($entry, $entries) ? 'registered' : 'inactive');

        return ['status' => $status, 'targets' => $status === 'registered' ? [[
            'catalog' => $catalog->value, 'canonical_id' => $canonicalId,
            'catalog_version' => $snapshot->descriptor->version, 'catalog_sha256' => $snapshot->descriptor->sha256,
            'entry_sha256' => $entry['sha256'],
        ]] : [], 'compatibility' => 'not_evaluated', 'human_review_required' => true,
            'usage_allowed' => false, 'publish_allowed' => false];
    }

    /** @param array<string, string> $context */
    public function taxonomyPath(CatalogSnapshot $snapshot, array $context): array
    {
        $kinds = ['protocol', 'scope', 'segment', 'category', 'consumption_type', 'material'];
        if ($snapshot->descriptor->catalog !== CatalogType::Taxonomy
            || array_diff($kinds, array_keys($context)) !== [] || array_diff(array_keys($context), $kinds) !== []) {
            throw new CatalogContractViolation('An exact six-kind taxonomy context is required.');
        }
        $nodes = array_column($snapshot->payload['nodes'], null, 'canonical_id');
        $targets = [];
        foreach ($kinds as $kind) {
            $result = $this->lookup($snapshot, $kind.':'.$context[$kind]);
            if ($result['status'] !== 'registered') {
                return $result;
            }
            $targets[] = $result['targets'][0];
        }
        foreach (['segment' => ['protocol:'.$context['protocol'], 'scope:'.$context['scope']],
            'category' => ['segment:'.$context['segment']], 'material' => ['consumption_type:'.$context['consumption_type']]] as $kind => $parents) {
            $actual = $nodes[$kind.':'.$context[$kind]]['parents'];
            sort($parents, SORT_STRING);
            sort($actual, SORT_STRING);
            if ($parents !== $actual) {
                return [...$result, 'status' => 'context_mismatch', 'targets' => []];
            }
        }
        $links = array_filter($snapshot->payload['category_consumption_links'], fn (array $link): bool => ! $link['deleted'] && $link['category_id'] === $context['category'] && $link['consumption_type_id'] === $context['consumption_type']);
        if (count($links) !== 1) {
            return [...$result, 'status' => 'context_mismatch', 'targets' => []];
        }
        $link = array_values($links)[0];

        return [...$result, 'targets' => $targets, 'assignment' => ['id' => $link['id'], 'sha256' => $link['sha256']]];
    }

    private function active(array $entry, array $entries): bool
    {
        if (! $entry['active'] || ($entry['deleted'] ?? false)) {
            return false;
        }
        foreach ($entry['parents'] ?? [] as $parent) {
            if (! isset($entries[$parent]) || ! $this->active($entries[$parent], $entries)) {
                return false;
            }
        }

        return true;
    }
}
