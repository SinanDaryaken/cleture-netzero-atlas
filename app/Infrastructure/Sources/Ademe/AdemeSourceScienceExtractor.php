<?php

namespace App\Infrastructure\Sources\Ademe;

use Brick\Math\BigRational;

class AdemeSourceScienceExtractor
{
    /** @param array<string, mixed> $payload @param array<string, string> $source @return array<string, mixed> */
    public function extract(array $payload, ?string $unit, ?string $value, array $source): array
    {
        $row = $payload['source_rows'][0] ?? [];
        $fields = $row['fields'] ?? [];
        $evidence = [];
        foreach (['Programme', 'Source', 'Url du programme', 'Nom frontière français', 'Nom frontière anglais',
            'Code de la catégorie', 'Unité français', 'Commentaire français', 'Commentaire anglais'] as $field) {
            if (($text = $this->text($fields, $field)) !== null) {
                $evidence[] = ['row' => $row['row'] ?? null, 'field' => $field, 'value' => $text];
            }
        }
        $reports = [];
        foreach (['Programme', 'Source', 'Code de la catégorie'] as $field) {
            $text = $this->text($fields, $field) ?? '';
            if (preg_match('/\b(?:IPCC|GIEC)\b/iu', $text) !== 1) {
                continue;
            }
            preg_match_all('/\bAR\h*([456])\b/iu', $text, $matches);
            foreach ($matches[1] as $number) {
                $reports[] = 'AR'.$number;
            }
            preg_match_all('/\b([456])(?:e|ème|eme)\h+rapport\h+(?:du\h+)?GIEC\b/iu', $text, $matches);
            foreach ($matches[1] as $number) {
                $reports[] = 'AR'.$number;
            }
        }
        $reports = array_values(array_unique($reports));
        $horizons = [];
        foreach (['Nom frontière français', 'Nom frontière anglais', 'Code de la catégorie'] as $field) {
            preg_match_all('/\b(?:PRG\h+à|GWP)\h*([0-9]{1,4})\h*(?:ans|years)\b/iu', $this->text($fields, $field) ?? '', $matches);
            foreach ($matches[1] as $years) {
                if ((int) $years > 0) {
                    $horizons[] = (int) $years;
                }
            }
        }
        $horizons = array_values(array_unique($horizons));
        $gwp = null;
        if ($reports !== [] || $horizons !== []) {
            $conflict = count($reports) > 1 || count($horizons) > 1;
            $gwp = [
                'status' => $conflict ? 'conflict' : (count($reports) === 1 && count($horizons) === 1 ? 'reported' : 'partial'),
                'assessment' => $reports !== [] ? 'IPCC' : null,
                'version' => count($reports) === 1 ? $reports[0] : null,
                'time_horizon_years' => count($horizons) === 1 ? $horizons[0] : null,
                'reference' => $this->text($fields, 'Source') ?? $this->text($fields, 'Programme'),
                'reported_versions' => $reports, 'reported_horizons' => $horizons,
            ];
        }
        $formula = $this->formula($fields);
        $coefficient = null;
        $isGwpRecord = preg_match('/^PRG\h+à\h+[0-9]+\h+ans$/iu', $this->text($fields, 'Nom frontière français') ?? '') === 1
            && str_starts_with($this->text($fields, 'Code de la catégorie') ?? '', 'Process et émissions fugitives > PRG à ');
        if ($isGwpRecord && ($gwp['status'] ?? null) !== 'conflict' && $unit === 'kgCO2e/kg'
            && $unit === $this->text($fields, 'Unité français') && $value !== null
            && preg_match('/^[0-9]+(?:\.[0-9]+)?$/D', $value) === 1 && $this->text($fields, 'Nom base français') !== null) {
            $coefficient = ['gas_name' => $this->text($fields, 'Nom base français'), 'value' => $value, 'unit' => $unit];
            foreach (['Nom base français', 'Total poste non décomposé'] as $field) {
                $evidence[] = ['row' => $row['row'] ?? null, 'field' => $field, 'value' => $this->text($fields, $field)];
            }
        }
        $missing = [];
        if ($gwp === null) {
            $missing[] = 'Kaynak kaydında açık GWP raporu veya zaman ufku bulunamadı.';
        } elseif ($gwp['status'] === 'partial') {
            $missing[] = 'GWP beyanı kısmi; eksik rapor veya zaman ufku tamamlanmadı.';
        } elseif ($gwp['status'] === 'conflict') {
            $missing[] = 'Kaynak alanlarında çelişen GWP raporu veya zaman ufku var; otomatik yöntem seçilmedi.';
        }
        if ($formula === null) {
            $missing[] = 'Kaynak kaydında açık bir üretim formülü beyanı bulunamadı; faaliyet × faktör ilişkisi kaynak formülü olarak yazılmadı.';
        } elseif ($formula['status'] === 'conflict') {
            $missing[] = 'Birden fazla farklı formül beyanı bulundu; otomatik formül seçilmedi.';
        } elseif ($formula['parameters'] === null || $formula['output_unit'] === null) {
            $missing[] = 'Formül metni bulundu; parametre veya sonuç birimleri kaynakta ayrıca belirtilmemiş.';
        }

        return [
            'schema_version' => 1, 'source' => $source,
            'coverage' => ['record_fields' => 'inspected', 'linked_documents' => 'not_fetched'],
            'source_unit' => $this->text($fields, 'Unité français'),
            'method' => ['program' => $this->text($fields, 'Programme'), 'reference' => $this->text($fields, 'Source'),
                'reference_url' => $this->text($fields, 'Url du programme')],
            'gwp' => $gwp, 'gwp_coefficient' => $coefficient, 'formula' => $formula,
            'heating_value' => $this->heatingValue($fields, $unit, $row['row'] ?? null),
            'evidence' => $evidence, 'missing' => $missing,
        ];
    }

    /** @param array<string, string> $fields @return array<string, mixed> */
    private function heatingValue(array $fields, ?string $unit, ?int $row): array
    {
        $sourceUnit = $this->text($fields, 'Unité français');
        preg_match_all('/\b(PCI|PCS)\b/i', $sourceUnit === $unit ? ($unit ?? '') : '', $matches);
        $bases = array_values(array_unique(array_map('strtolower', $matches[1])));
        $ratios = [];
        $evidence = [];
        if ($bases !== []) {
            $evidence[] = ['row' => $row, 'field' => 'Unité français', 'value' => $sourceUnit];
        }
        foreach (['Commentaire français', 'Commentaire anglais'] as $field) {
            preg_match_all('/^\h*(?:Rapport\h+|Ratio\h+)?PCS\h*\/\h*PCI\h*[:=]\h*([0-9]{1,3}(?:[.,][0-9]{1,12})?)\h*$/miu',
                $this->text($fields, $field) ?? '', $matches);
            foreach ($matches[1] as $value) {
                $number = BigRational::of(str_replace(',', '.', $value));
                $ratios[(string) $number] = $number->isGreaterThanOrEqualTo(1) ? str_replace(',', '.', $value) : null;
                $evidence[] = ['row' => $row, 'field' => $field, 'value' => $this->text($fields, $field)];
            }
        }
        $fuel = $this->text($fields, 'Nom base français');
        if ($ratios !== [] && $fuel !== null) {
            $evidence[] = ['row' => $row, 'field' => 'Nom base français', 'value' => $fuel];
        }
        $conflict = count($bases) > 1 || count($ratios) > 1 || in_array(null, $ratios, true);

        return ['status' => $conflict ? 'conflict' : (count($ratios) === 1 && $fuel !== null ? 'reported' : 'partial'),
            'basis' => count($bases) === 1 ? $bases[0] : null,
            'pcs_per_pci' => ! $conflict && count($ratios) === 1 && $fuel !== null ? array_values($ratios)[0] : null,
            'fuel' => $fuel, 'evidence' => $evidence];
    }

    /** @param array<string, string> $fields @return array<string, mixed>|null */
    private function formula(array $fields): ?array
    {
        $declarations = [];
        foreach (['Commentaire français', 'Commentaire anglais'] as $field) {
            $text = $this->text($fields, $field) ?? '';
            preg_match_all('/^\h*(?:Formule(?: de calcul)?|Formula)\h*:\h*(.+)$/miu', $text, $matches);
            foreach ($matches[1] as $expression) {
                $declarations[trim($expression)][] = $text;
            }
        }
        if ($declarations === []) {
            return null;
        }
        if (count($declarations) !== 1) {
            return ['status' => 'conflict', 'text' => null, 'parameters' => null, 'output_unit' => null,
                'executable' => false, 'declarations' => array_keys($declarations)];
        }
        $expression = (string) array_key_first($declarations);
        $text = implode("\n", array_unique($declarations[$expression]));
        $parameters = [];
        preg_match_all('/^\h*(?:Paramètre|Parameter)\h+([\p{L}_][\p{L}\p{N}_]*)\h*:\h*([^\r\n]+)$/miu', $text, $matches, PREG_SET_ORDER);
        foreach ($matches as $match) {
            $parameters[$match[1]][] = trim($match[2]);
        }
        $rows = [];
        foreach ($parameters as $symbol => $units) {
            $units = array_values(array_unique($units));
            if (count($units) !== 1) {
                $rows = [];
                break;
            }
            $rows[] = ['symbol' => $symbol, 'unit' => $units[0]];
        }
        preg_match_all('/^\h*(?:Unité du résultat|Output unit)\h*:\h*([^\r\n]+)$/miu', $text, $matches);
        $outputUnits = array_values(array_unique(array_map('trim', $matches[1])));

        return ['status' => 'reported', 'text' => $expression, 'parameters' => $rows === [] ? null : $rows,
            'output_unit' => count($outputUnits) === 1 ? $outputUnits[0] : null, 'executable' => false];
    }

    /** @param array<string, mixed> $fields */
    private function text(array $fields, string $key): ?string
    {
        $value = $fields[$key] ?? null;

        return is_string($value) && trim($value) !== '' ? trim($value) : null;
    }
}
