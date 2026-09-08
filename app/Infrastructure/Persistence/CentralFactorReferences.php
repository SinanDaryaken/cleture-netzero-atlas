<?php

namespace App\Infrastructure\Persistence;

use Illuminate\Database\Connection;

class CentralFactorReferences
{
    /** @var array<string, array<string, array<string, mixed>>> */
    private array $units = [];

    /** @var array<string, array<string, array<string, mixed>>> */
    private array $countries = [];

    public function load(Connection $db): void
    {
        $this->units = [];
        $this->countries = [];
        $release = $db->table('unit_catalog_releases')->where('status', 'published')
            ->orderByDesc('published_at')->orderByDesc('id')->value('id');
        if ($release !== null) {
            $definitions = $db->table('unit_definition_versions as definition')
                ->join('unit_types as unit', 'unit.id', '=', 'definition.unit_type_id')
                ->where('definition.unit_catalog_release_id', $release)
                ->where('unit.active', true)->whereNull('unit.deleted_at')
                ->get(['definition.unit_type_id', 'definition.unit_code_snapshot', 'definition.unit_symbol_snapshot']);
            foreach ($definitions as $definition) {
                foreach ([$definition->unit_code_snapshot, $definition->unit_symbol_snapshot] as $label) {
                    if (is_string($label) && $label !== '') {
                        $this->units[$label][$definition->unit_type_id] = [
                            'id' => $definition->unit_type_id, 'code' => $definition->unit_code_snapshot,
                            'symbol' => $definition->unit_symbol_snapshot, 'release_id' => $release,
                        ];
                    }
                }
            }
        }
        foreach ($db->table('countries')->where('active', true)->whereNull('deleted_at')->get(['id', 'iso2', 'iso3']) as $country) {
            $entry = ['id' => $country->id, 'code' => $country->iso2];
            foreach ([$country->iso2, $country->iso3] as $label) {
                $this->countries[mb_strtolower($label)][$country->id] = $entry;
            }
        }
        $names = $db->table('country_translations as translation')
            ->join('countries as country', 'country.id', '=', 'translation.country_id')
            ->join('languages as language', 'language.id', '=', 'translation.language_id')
            ->where('country.active', true)->whereNull('country.deleted_at')
            ->where('language.active', true)->whereNull('language.deleted_at')
            ->get(['country.id', 'country.iso2', 'translation.name']);
        foreach ($names as $name) {
            $this->countries[mb_strtolower(trim($name->name))][$name->id] = ['id' => $name->id, 'code' => $name->iso2];
        }
    }

    /** @return array{status: string, reference: array<string, mixed>|null} */
    public function unit(?string $label): array
    {
        return $this->resolve($this->units[$label ?? ''] ?? []);
    }

    /** @return array{status: string, reference: array<string, mixed>|null} */
    public function country(?string $label): array
    {
        return $this->resolve($this->countries[mb_strtolower(trim($label ?? ''))] ?? []);
    }

    /**
     * @param  array<string, array<string, mixed>>  $matches
     * @return array{status: string, reference: array<string, mixed>|null}
     */
    private function resolve(array $matches): array
    {
        return ['status' => count($matches) === 1 ? 'matched' : ($matches === [] ? 'unresolved' : 'ambiguous'),
            'reference' => count($matches) === 1 ? array_values($matches)[0] : null];
    }
}
