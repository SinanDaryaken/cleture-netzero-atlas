<?php

namespace Tests\Unit\Infrastructure\Candidate;

use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Candidate\StoredNormalizedArtifact;
use App\Infrastructure\Candidate\LaravelCandidateDraftReader;
use Illuminate\Filesystem\FilesystemManager;
use Illuminate\Support\Facades\Storage;
use Tests\TestCase;

final class LaravelCandidateDraftReaderTest extends TestCase
{
    public function test_reads_a_complete_v2_draft_after_verifying_the_persisted_identity(): void
    {
        Storage::fake('atlas_processing');
        [$artifact, $line] = $this->artifact();
        Storage::disk('atlas_processing')->put($artifact->objectKey, $line);

        $drafts = iterator_to_array($this->reader()->read($artifact), false);

        $this->assertCount(1, $drafts);
        $this->assertSame('2.0.0', $drafts[0]->schemaVersion);
        $this->assertSame('candidate-1', $drafts[0]->candidateKey);
    }

    public function test_rejects_draft_bytes_that_changed_after_persistence(): void
    {
        Storage::fake('atlas_processing');
        [$artifact, $line] = $this->artifact();
        Storage::disk('atlas_processing')->put(
            $artifact->objectKey,
            str_replace('candidate-1', 'candidate-2', $line),
        );

        $this->expectException(CandidateContractViolation::class);
        $this->expectExceptionMessage('artifact identity does not match persistence');

        iterator_to_array($this->reader()->read($artifact), false);
    }

    private function reader(): LaravelCandidateDraftReader
    {
        return new LaravelCandidateDraftReader(app(FilesystemManager::class));
    }

    /** @return array{StoredNormalizedArtifact, string} */
    private function artifact(): array
    {
        $line = json_encode($this->draft()->toUnhashedRecord(), JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES)."\n";

        return [
            new StoredNormalizedArtifact(
                disk: 'atlas_processing',
                objectKey: 'normalized/v2.ndjson',
                format: 'ndjson',
                normalizerVersion: '1.0.0',
                candidateSchemaVersion: '2.0.0',
                candidateSchemaSha256: str_repeat('a', 64),
                candidateCount: 1,
                findingCount: 0,
                fileSize: strlen($line),
                sha256: hash('sha256', $line),
                alreadyExisted: false,
            ),
            $line,
        ];
    }

    private function draft(): CandidateEntityDraft
    {
        return new CandidateEntityDraft(
            schemaVersion: '2.0.0',
            candidateKey: 'candidate-1',
            logicalKey: 'logical-1',
            variantKey: 'variant-1',
            valueKind: 'co2e_total',
            intendedUse: ['source_unspecified'],
            localizedTexts: [['locale' => 'fr']],
            sourceTaxonomy: [['scheme' => 'ADEME']],
            primaryComponentKey: 'component-1',
            primaryQuantity: [],
            components: [['component_key' => 'component-1']],
            temporal: [],
            methodology: [],
            geographyProposals: [],
            canonicalMappingProposals: [],
            reportingApplicabilityProposals: [],
            relationships: [],
            evidence: [['evidence_key' => 'evidence-1']],
            provenance: [['provenance_key' => 'provenance-1']],
            extensions: [],
        );
    }
}
