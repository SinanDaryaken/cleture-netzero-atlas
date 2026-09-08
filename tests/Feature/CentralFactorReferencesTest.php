<?php

namespace Tests\Feature;

use App\Infrastructure\Persistence\CentralFactorReferences;
use App\Infrastructure\Sources\Ademe\AdemeAdminReferenceMapper;
use Illuminate\Database\Connection;
use Mockery;
use Tests\TestCase;

class CentralFactorReferencesTest extends TestCase
{
    public function test_science_separates_gas_contributions_and_stages_without_recalculating_values(): void
    {
        $payload = ['source_rows' => [
            ['row' => 12, 'type' => 'Elément', 'fields' => ['Unité français' => 'kgCO2e/kg', 'Structure' => 'élément décomposé par poste et par gaz']],
            ['row' => 13, 'type' => 'Poste', 'fields' => ['Unité français' => 'kgCO2e/kg', 'Type poste' => 'Amont']],
        ], 'components' => [
            ['component_key' => 'x:component:total', 'basis' => 'source_reported_total', 'quantity' => ['value' => '3.2200', 'output_unit' => ['raw_label' => 'kgCO2e/kg']]],
            ['component_key' => 'x:component:gas:ch4', 'basis' => 'source_reported_gas_component', 'quantity' => ['value' => '0.134', 'output_unit' => ['raw_label' => 'kgCO2e/kg']]],
            ['component_key' => 'x:component:lifecycle:1', 'basis' => 'lifecycle_stage', 'quantity' => ['value' => '0.498', 'output_unit' => ['raw_label' => 'kgCO2e/kg']]],
            ['component_key' => 'x:component:lifecycle:1:gas:co2', 'basis' => 'lifecycle_stage_gas_component', 'quantity' => ['value' => '0.365', 'output_unit' => ['raw_label' => 'kgCO2e/kg']]],
        ]];
        $before = $payload;
        $mapper = new AdemeAdminReferenceMapper(Mockery::mock(CentralFactorReferences::class));
        $result = $mapper->science($payload);
        $this->assertSame($before, $payload);
        $this->assertTrue($result['stage_decomposition']);
        $this->assertSame(1, $result['source_stage_count']);
        $this->assertSame('Amont', $result['groups'][1]['label']);
        $this->assertSame(13, $result['groups'][1]['source_row']);
        $this->assertSame('co2e_contribution', $result['groups'][0]['components'][1]['measurement']);
        $this->assertSame('co2e_total', $result['groups'][1]['components'][0]['measurement']);
        $this->assertCount(2, $result['groups'][1]['components']);
        $this->assertArrayNotHasKey('gwp', $result);
        $payload['components'][1]['quantity']['output_unit']['raw_label'] = 'kgCH4/kg';
        $this->assertSame('unknown', $mapper->science($payload)['groups'][0]['components'][1]['measurement']);
        $payload['source_rows'][0]['fields']['Structure'] = 'unknown';
        $this->assertFalse($mapper->science($payload)['stage_decomposition']);
    }

    public function test_mapper_loads_and_uses_the_same_reference_catalog_instance(): void
    {
        $references = Mockery::mock(CentralFactorReferences::class);
        $connection = Mockery::mock(Connection::class);
        $references->shouldReceive('load')->once()->with($connection)->ordered();
        $references->shouldReceive('unit')->once()->with('kg')->ordered()->andReturn(['status' => 'matched', 'reference' => ['code' => 'kg']]);
        $references->shouldReceive('unit')->once()->with('kWh')->ordered()->andReturn(['status' => 'matched', 'reference' => ['code' => 'kWh']]);
        $mapper = new AdemeAdminReferenceMapper($references);
        $mapper->loadReferences($connection);
        $this->assertSame('matched', $mapper->unit('kgCO2e/kWh')['status']);
    }

    public function test_unit_binding_preserves_the_source_denominator(): void
    {
        $references = Mockery::mock(CentralFactorReferences::class);
        $references->shouldReceive('unit')->once()->with('kg')->andReturn(['status' => 'matched', 'reference' => ['code' => 'kg']]);
        $references->shouldReceive('unit')->once()->with('100 km')->andReturn(['status' => 'unresolved', 'reference' => null]);
        $result = (new AdemeAdminReferenceMapper($references))->unit('kgCO2e/100 km');
        $this->assertSame('100 km', $result['activity_label']);
        $this->assertSame('unresolved', $result['status']);
        $this->assertSame('kgCO2e/100 km', $result['source_label']);
    }

    public function test_unknown_unit_does_not_guess_a_mass_or_activity(): void
    {
        $references = Mockery::mock(CentralFactorReferences::class);
        $references->shouldNotReceive('unit');
        $result = (new AdemeAdminReferenceMapper($references))->unit('unknown');
        $this->assertNull($result['output']);
        $this->assertNull($result['activity']);
    }

    public function test_net_weight_qualifier_is_preserved_when_kilogram_is_linked(): void
    {
        $references = Mockery::mock(CentralFactorReferences::class);
        $references->shouldReceive('unit')->twice()->with('kg')->andReturn(['status' => 'matched', 'reference' => ['code' => 'kg']]);
        $result = (new AdemeAdminReferenceMapper($references))->unit('kgCO2e/kg de poids net');
        $this->assertSame('partial', $result['status']);
        $this->assertSame('kg de poids net', $result['activity_label']);
        $this->assertSame('kg', $result['activity']['reference']['code']);
    }

    public function test_mainland_france_is_linked_without_expanding_its_scope(): void
    {
        $references = Mockery::mock(CentralFactorReferences::class);
        $references->shouldReceive('country')->with('FR')->andReturn(['status' => 'matched', 'reference' => ['code' => 'FR']]);
        $result = (new AdemeAdminReferenceMapper($references))->geography(['Localisation géographique' => 'France continentale']);
        $this->assertSame('partial', $result['status']);
        $this->assertSame('France continentale', $result['source_location']);
        $this->assertSame('FR', $result['country']['code']);
    }

    public function test_country_match_does_not_erase_a_narrower_source_region(): void
    {
        $references = Mockery::mock(CentralFactorReferences::class);
        $references->shouldReceive('country')->with('France')->andReturn(['status' => 'matched', 'reference' => ['code' => 'FR']]);
        $result = (new AdemeAdminReferenceMapper($references))->geography([
            'Localisation géographique' => 'France', 'Sous-localisation géographique français' => 'Corse',
        ]);
        $this->assertSame('partial', $result['status']);
        $this->assertSame('Corse', $result['source_sub_location']);
        $this->assertSame('FR', $result['country']['code']);
    }
}
