<?php

namespace Tests\Feature;

use App\Infrastructure\Sources\Ademe\AdemeSourceScienceExtractor;
use Tests\TestCase;

class CentralFactorSourceScienceTest extends TestCase
{
    public function test_explicit_heating_basis_ratio_and_row_evidence_are_preserved(): void
    {
        $payload = $this->payload(['Unité français' => 'kgCO2e/kWh PCI', 'Nom base français' => 'Gaz naturel',
            'Commentaire français' => "Rapport PCS/PCI : 1,100\nDescription du combustible"]);
        $result = $this->extract($payload, 'kgCO2e/kWh PCI')['heating_value'];
        $this->assertSame('pci', $result['basis']);
        $this->assertSame('1.100', $result['pcs_per_pci']);
        $this->assertSame('Gaz naturel', $result['fuel']);
        $this->assertSame('reported', $result['status']);
        $this->assertSame(123, $result['evidence'][0]['row']);
        $this->assertSame('Unité français', $result['evidence'][0]['field']);
        $this->assertNull($this->extract($this->payload(['Unité français' => 'kgCO2e/kWh PCS']), 'kgCO2e/kWh PCS')['heating_value']['pcs_per_pci']);
    }

    public function test_heating_ratios_are_not_guessed_from_mentions_or_chosen_when_conflicting(): void
    {
        foreach (["PCS/PCI : 1.1\nPCS/PCI : 1.2", 'PCS/PCI : 0.9'] as $text) {
            $result = $this->extract($this->payload(['Commentaire français' => $text]))['heating_value'];
            $this->assertSame('conflict', $result['status']);
            $this->assertNull($result['pcs_per_pci']);
        }
        foreach (['Le PCS est supérieur au PCI de 11%', 'PCS/PCI : 1.1%'] as $text) {
            $this->assertNull($this->extract($this->payload(['Commentaire français' => $text]))['heating_value']['pcs_per_pci']);
        }
        $this->assertNull($this->extract($this->payload(['Commentaire français' => 'PCS/PCI : 1.1', 'Nom base français' => '']))['heating_value']['pcs_per_pci']);
        $result = $this->extract($this->payload(['Commentaire français' => "PCS/PCI : 1.1\nPCS/PCI : 1.100"]))['heating_value'];
        $this->assertSame('reported', $result['status']);
    }

    /** @return array<string, mixed> */
    private function payload(array $overrides = []): array
    {
        return ['source_rows' => [['row' => 123, 'type' => 'Elément', 'fields' => array_replace([
            'Programme' => '6ème rapport du GIEC (2023)', 'Source' => 'GIEC (AR6 - 2023)',
            'Nom frontière français' => 'PRG à 100 ans', 'Nom frontière anglais' => 'GWP 100 years',
            'Code de la catégorie' => 'Process et émissions fugitives > PRG à 100 ans issus du 6eme rapport du GIEC > Autres Gaz divers',
            'Nom base français' => '(e)-hex-2-en-1-ol', 'Unité français' => 'kgCO2e/kg',
            'Total poste non décomposé' => '2,00E-03', 'Url du programme' => 'https://www.ipcc.ch/source-reference.p',
        ], $overrides)]]];
    }

    /** @return array<string, mixed> */
    private function extract(array $payload, ?string $unit = 'kgCO2e/kg', ?string $value = '0.00200'): array
    {
        return (new AdemeSourceScienceExtractor)->extract($payload, $unit, $value,
            ['provider' => 'ADEME', 'dataset' => 'base-carboner', 'version' => '23.6', 'artifact_sha256' => str_repeat('a', 64)]);
    }

    public function test_explicit_gwp_record_provides_report_horizon_own_coefficient_and_original_evidence(): void
    {
        $payload = $this->payload();
        $before = $payload;
        $result = $this->extract($payload);
        $this->assertSame('reported', $result['gwp']['status']);
        $this->assertSame('IPCC', $result['gwp']['assessment']);
        $this->assertSame('AR6', $result['gwp']['version']);
        $this->assertSame(100, $result['gwp']['time_horizon_years']);
        $this->assertSame('0.00200', $result['gwp_coefficient']['value']);
        $this->assertSame('(e)-hex-2-en-1-ol', $result['gwp_coefficient']['gas_name']);
        $this->assertSame('2,00E-03', collect($result['evidence'])->firstWhere('field', 'Total poste non décomposé')['value']);
        $this->assertSame(123, $result['evidence'][0]['row']);
        $this->assertSame('https://www.ipcc.ch/source-reference.p', $result['method']['reference_url']);
        $this->assertSame('not_fetched', $result['coverage']['linked_documents']);
        $this->assertSame('23.6', $result['source']['version']);
        $this->assertNull($result['formula']);
        $this->assertSame($before, $payload);
    }

    public function test_generic_factor_does_not_inherit_a_report_or_turn_emission_value_into_a_gwp(): void
    {
        $result = $this->extract($this->payload(['Programme' => 'WRI', 'Source' => 'ADEME',
            'Nom frontière français' => 'Combustion', 'Nom frontière anglais' => '', 'Code de la catégorie' => 'Combustibles',
            'Commentaire français' => 'Comparaison avec AR5 et AR6, PRG à 100 ans.']));
        $this->assertNull($result['gwp']);
        $this->assertNull($result['gwp_coefficient']);
        $this->assertNull($result['formula']);
        $this->assertSame('kgCO2e/kg', $result['source_unit']);
    }

    public function test_incomplete_and_conflicting_source_declarations_are_not_completed_by_guessing(): void
    {
        $partial = $this->extract($this->payload(['Nom frontière français' => '', 'Nom frontière anglais' => '', 'Code de la catégorie' => 'Gaz']));
        $this->assertSame('partial', $partial['gwp']['status']);
        $this->assertSame('AR6', $partial['gwp']['version']);
        $this->assertNull($partial['gwp']['time_horizon_years']);
        $conflict = $this->extract($this->payload(['Source' => 'IPCC AR5']));
        $this->assertSame('conflict', $conflict['gwp']['status']);
        $this->assertNull($conflict['gwp']['version']);
        $this->assertNull($conflict['gwp_coefficient']);
        $conflict = $this->extract($this->payload(['Nom frontière anglais' => 'GWP 20 years']));
        $this->assertSame('conflict', $conflict['gwp']['status']);
        $this->assertNull($conflict['gwp']['time_horizon_years']);
    }

    public function test_gwp_coefficient_requires_its_specific_record_scope_unit_and_known_nonnegative_value(): void
    {
        foreach ([null, '-1', 'not-a-number'] as $value) {
            $this->assertNull($this->extract($this->payload(), value: $value)['gwp_coefficient']);
        }
        $this->assertSame('0', $this->extract($this->payload(), value: '0')['gwp_coefficient']['value']);
        $this->assertNull($this->extract($this->payload(), unit: 'kgCO2e/t')['gwp_coefficient']);
        $this->assertNull($this->extract($this->payload(['Code de la catégorie' => 'Combustibles']))['gwp_coefficient']);
    }

    public function test_formula_text_and_explicit_parameter_units_are_preserved_without_execution(): void
    {
        $result = $this->extract($this->payload(['Commentaire français' => "Formule de calcul : E = q * f\nParamètre q : kWh PCI\nParamètre f : kgCO2e/kWh PCI\nUnité du résultat : kgCO2e"]));
        $this->assertSame('E = q * f', $result['formula']['text']);
        $this->assertSame([['symbol' => 'q', 'unit' => 'kWh PCI'], ['symbol' => 'f', 'unit' => 'kgCO2e/kWh PCI']], $result['formula']['parameters']);
        $this->assertSame('kgCO2e', $result['formula']['output_unit']);
        $this->assertFalse($result['formula']['executable']);
        $partial = $this->extract($this->payload(['Commentaire français' => 'Formule : E = q * f']));
        $this->assertNull($partial['formula']['parameters']);
        $this->assertNull($partial['formula']['output_unit']);
    }

    public function test_conflicting_formulas_and_units_remain_unresolved_and_script_text_is_never_executed(): void
    {
        $result = $this->extract($this->payload(['Commentaire français' => "Formule : E = q * f\nFormule : E = q + f"]));
        $this->assertSame('conflict', $result['formula']['status']);
        $this->assertNull($result['formula']['text']);
        $result = $this->extract($this->payload(['Commentaire français' => "Formule : <script>invalid()</script>\nParamètre q : kg\nParamètre q : L"]));
        $this->assertSame('<script>invalid()</script>', $result['formula']['text']);
        $this->assertNull($result['formula']['parameters']);
        $this->assertFalse($result['formula']['executable']);
    }
}
