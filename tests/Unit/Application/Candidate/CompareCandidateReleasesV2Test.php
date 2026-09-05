<?php

namespace Tests\Unit\Application\Candidate;

use App\Application\Candidate\BuildCanonicalCandidateEntity;
use App\Application\Candidate\CompareCandidateReleases;
use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Candidate\CandidateSourceDiff;
use Tests\Support\CandidateFixture;
use Tests\TestCase;

final class CompareCandidateReleasesV2Test extends TestCase
{
    public function test_routes_mapping_changes_by_their_domain_and_quantity_units_to_unit(): void
    {
        $before = CandidateFixture::draft()->toUnhashedRecord();
        $after = $before;
        $after['canonical_mapping_proposals'][1]['source_value'] = 'changed taxonomy';
        $after['canonical_mapping_proposals'][2]['source_value'] = 'changed intended use';
        $after['primary_quantity']['output_unit']['raw_label'] = 'g';

        $diff = $this->compare($before, $after);
        $domains = array_column($diff->changes, 'domain', 'json_pointer');

        $this->assertSame('taxonomy', $domains['/canonical_mapping_proposals/1/source_value']);
        $this->assertSame('applicability', $domains['/canonical_mapping_proposals/2/source_value']);
        $this->assertSame('unit', $domains['/primary_quantity/output_unit/raw_label']);
    }

    public function test_only_release_scoped_references_are_normalized(): void
    {
        $before = CandidateFixture::draft('test:factor:release:1')->toUnhashedRecord();
        $after = CandidateFixture::draft('test:factor:release:2')->toUnhashedRecord();
        $this->assertSame('unchanged', $this->compare($before, $after)->classification);
        $before['localized_texts'][0]['description'] = 'Source says test:factor:release:1';
        $after['localized_texts'][0]['description'] = 'Source says test:factor:release:2';

        $diff = $this->compare($before, $after);

        $this->assertSame('changed', $diff->classification);
        $this->assertSame('Source says test:factor:release:1', $diff->changes[0]['before']['value']);
        $this->assertSame('Source says test:factor:release:2', $diff->changes[0]['after']['value']);
    }

    private function compare(array $before, array $after): CandidateSourceDiff
    {
        $before['extensions'] = (array) $before['extensions'];
        $after['extensions'] = (array) $after['extensions'];
        $builder = app(BuildCanonicalCandidateEntity::class);

        return app(CompareCandidateReleases::class)->handle(
            [$builder->handle(CandidateEntityDraft::fromUnhashedRecord($after))],
            [$builder->handle(CandidateEntityDraft::fromUnhashedRecord($before))],
        )[0];
    }
}
