<?php

namespace App\Infrastructure\Sources\Ademe;

use App\Infrastructure\Persistence\CentralFactorReferences;
use Illuminate\Database\Connection;

class AdemeAdminReferenceMapper
{
    public function __construct(private CentralFactorReferences $references, private AdemeSourceScienceExtractor $sourceScience = new AdemeSourceScienceExtractor) {}

    /** @param array<string, mixed> $payload @param array<string, string> $source @return array<string, mixed> */
    public function sourceScience(array $payload, ?string $unit, ?string $value, array $source): array
    {
        return $this->sourceScience->extract($payload, $unit, $value, $source);
    }

    public function sourceCode(): string
    {
        return 'ADEME';
    }

    public function loadReferences(Connection $connection): void
    {
        $this->references->load($connection);
    }

    /** @param array<string, mixed> $payload @return array<string, mixed> */
    public function science(array $payload): array
    {
        $sourceRows = $payload['source_rows'] ?? [];
        $primary = $sourceRows[0] ?? [];
        $posts = array_values(array_filter($sourceRows, fn (array $row): bool => $row['type'] === 'Poste'));
        $groups = [0 => ['label' => 'Faktör toplamı ve gaz kırılımı', 'role' => 'factor',
            'source_row' => $primary['row'] ?? null, 'components' => []]];
        foreach ($posts as $index => $post) {
            $groups[$index + 1] = ['label' => trim(implode(' · ', array_filter([
                $post['fields']['Type poste'] ?? '', $post['fields']['Nom poste français'] ?? '',
            ]))) ?: 'Aşama '.($index + 1), 'role' => 'stage', 'source_row' => $post['row'], 'components' => []];
        }
        foreach ($payload['components'] ?? [] as $component) {
            $basis = $component['basis'] ?? '';
            $index = 0;
            if (in_array($basis, ['lifecycle_stage', 'lifecycle_stage_gas_component'], true)) {
                if (! preg_match('/:component:lifecycle:([0-9]+)(?::gas:.*)?$/D', $component['component_key'], $matches)) {
                    continue;
                }
                $index = (int) $matches[1];
            }
            if (! isset($groups[$index])) {
                continue;
            }
            $unit = $component['quantity']['output_unit']['raw_label'] ?? '';
            $sourceUnit = ($index === 0 ? $primary : $posts[$index - 1])['fields']['Unité français'] ?? '';
            $known = str_starts_with($unit ?? '', 'kgCO2e/') && strlen($unit) > 7 && $sourceUnit === $unit;
            $isGas = in_array($basis, ['source_reported_gas_component', 'lifecycle_stage_gas_component'], true);
            $isTotal = in_array($basis, ['source_reported_total', 'lifecycle_stage'], true);
            $groups[$index]['components'][] = ['key' => $component['component_key'],
                'measurement' => $known && ($isGas || $isTotal) ? ($isGas ? 'co2e_contribution' : 'co2e_total') : 'unknown'];
        }

        return [
            'schema_version' => 1, 'basis' => 'ademe_export_unit_and_structure',
            'note' => 'ADEME dışa aktarımındaki birim ve satır yapısına göre yorumlanmıştır. CO₂e gaz katkıları gaz kütlesi değildir; GWP yeniden uygulanmaz. Eksik gaz alanları sıfır kabul edilmez. CO₂b ayrıca gösterilir; toplam kapsamına otomatik eklenmez.',
            'stage_decomposition' => in_array($primary['fields']['Structure'] ?? '', [
                'élément décomposé par poste', 'élément décomposé par poste et par gaz',
            ], true),
            'source_stage_count' => count($posts), 'groups' => array_values($groups),
        ];
    }

    /** @return array<string, mixed> */
    public function unit(?string $sourceLabel): array
    {
        if ($sourceLabel === null || ! str_starts_with($sourceLabel, 'kgCO2e/')) {
            return ['status' => 'unresolved', 'source_label' => $sourceLabel, 'output' => null, 'activity' => null];
        }
        $activityLabel = substr($sourceLabel, strlen('kgCO2e/'));
        $unitCode = match ($activityLabel) {
            'tonne', 'tonne de déchets' => 't',
            'litre' => 'L',
            'kg de poids net', 'kg de poids vif' => 'kg',
            'kWh PCI', 'kWh PCS' => 'kWh',
            'GJ PCI', 'GJ PCS' => 'GJ',
            default => $activityLabel,
        };
        $hasQualifier = in_array($activityLabel, ['tonne de déchets', 'kg de poids net', 'kg de poids vif',
            'kWh PCI', 'kWh PCS', 'GJ PCI', 'GJ PCS'], true);
        $output = $this->references->unit('kg');
        $activity = $this->references->unit($unitCode);

        return [
            'status' => $output['status'] === 'matched' && $activity['status'] === 'matched' ? ($hasQualifier ? 'partial' : 'matched') : 'unresolved',
            'source_label' => $sourceLabel, 'indicator' => 'CO2e',
            'output' => $output, 'activity' => $activity,
            'activity_label' => $activityLabel,
            'note' => 'Kaynak değeri ve paydası korunur; bu eşleşme birim kimliğidir, dönüşüm veya kullanım onayı değildir.',
        ];
    }

    /** @param array<string, string> $fields @return array<string, mixed> */
    public function geography(array $fields): array
    {
        $location = trim($fields['Localisation géographique'] ?? '');
        $subLocation = trim($fields['Sous-localisation géographique français'] ?? '');
        $isMainlandFrance = $location === 'France continentale';
        $country = $this->references->country($isMainlandFrance ? 'FR' : $location);

        return [
            'status' => $country['status'] === 'matched' && ($subLocation !== '' || $isMainlandFrance) ? 'partial' : $country['status'],
            'country' => $country['reference'], 'source_location' => $location,
            'source_sub_location' => $subLocation,
            'note' => $isMainlandFrance ? 'Fransa ülke bağlantısı kuruldu; kaynağın France continentale kapsamı ayrıca korunuyor.'
                : ($subLocation !== '' ? 'Kaynağın alt bölge kapsamı korunuyor; ülke eşleşmesi alt bölge eşleşmesi değildir.' : null),
        ];
    }
}
