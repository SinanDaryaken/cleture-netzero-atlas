<?php

namespace Tests\Unit\Domain\Candidate;

use App\Application\Contracts\CandidateValidationRulesetLoader;
use App\Domain\Candidate\CandidateRecordReferences;
use App\Domain\Candidate\CandidateSemanticValidation;
use App\Domain\Catalog\CatalogType;
use App\Infrastructure\Candidate\JsonCandidateValidationRulesetLoader;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\Support\CandidateFixture;
use Tests\TestCase;

final class CandidateSemanticValidationTest extends TestCase
{
    public function test_keeps_unresolved_mappings_blocking_without_breaking_package_integrity(): void
    {
        $rules = app(CandidateValidationRulesetLoader::class)->load();
        $findings = $this->inspect(CandidateFixture::draft()->toUnhashedRecord());

        $this->assertCount(4, $findings);
        foreach ($findings as $finding) {
            $this->assertSame('mapping_unresolved', $finding->code);
            $this->assertSame('blocking', $finding->severity);
            $this->assertFalse($rules->document['rules'][$finding->code]['package_block']);
        }
    }

    #[DataProvider('defects')]
    public function test_reports_semantic_defects_with_a_field_pointer(string $defect, string $expected): void
    {
        $record = CandidateFixture::draft()->toUnhashedRecord();
        switch ($defect) {
            case 'reference': $record['components'][0]['methodology_ref'] = 'missing';
                break;
            case 'duplicate': $record['components'][] = $record['components'][0];
                break;
            case 'lineage': $record['provenance'][0]['source_asset_sha256'] = str_repeat('f', 64);
                break;
            case 'pointer': $record['provenance'][0]['field_pointers'] = ['/missing'];
                break;
            case 'coarse': $record['provenance'][0]['field_pointers'] = [''];
                break;
            case 'status': $record['canonical_mapping_proposals'][0]['status'] = 'proposed';
                break;
            case 'date': $record['temporal']['validity'] = ['valid_from' => '2025-01-01', 'valid_to' => '2024-01-01'];
                break;
            case 'period': $record['temporal']['reference_period']['start'] = '2024-01-01';
                break;
            case 'primary': $record['primary_quantity']['value'] = '99';
                break;
            case 'formula': $record['methodology']['formula_or_recipe_ref'] = 'formula:unknown';
                break;
        }

        $findings = $this->inspect($record);

        $matching = array_values(array_filter($findings, fn ($finding) => $finding->code === $expected));
        $this->assertNotEmpty($matching);
        $this->assertStringStartsWith('/', $matching[0]->jsonPointer);
    }

    public static function defects(): array
    {
        return [['reference', 'reference_invalid'], ['duplicate', 'reference_invalid'], ['lineage', 'provenance_invalid'],
            ['pointer', 'provenance_invalid'], ['coarse', 'provenance_coarse'], ['status', 'mapping_invalid'],
            ['date', 'temporal_invalid'], ['period', 'temporal_invalid'], ['primary', 'primary_component_mismatch'], ['formula', 'formula_unverified']];
    }

    public function test_rejects_a_target_from_a_different_snapshot(): void
    {
        $record = CandidateFixture::draft()->toUnhashedRecord();
        $record['canonical_mapping_proposals'][0]['status'] = 'proposed';
        $record['canonical_mapping_proposals'][0]['target'] = ['catalog' => 'unit', 'canonical_id' => CandidateFixture::UNIT_ID,
            'catalog_version' => 'wrong', 'catalog_sha256' => str_repeat('f', 64)];

        $this->assertContains('mapping_invalid', array_column($this->inspect($record), 'code'));
    }

    private function inspect(array $record): array
    {
        $rules = (new JsonCandidateValidationRulesetLoader(config('atlas.rulesets.candidate_validation.path'), config('atlas.rulesets.candidate_validation.sha256')))->load();

        return (new CandidateSemanticValidation(new CandidateRecordReferences))->inspect($record, $rules,
            CandidateFixture::snapshot(CatalogType::Unit), CandidateFixture::snapshot(CatalogType::Geography),
            [['asset_key' => 'sources/test/raw.csv', 'sha256' => hash('sha256', 'test raw')]]);
    }
}
