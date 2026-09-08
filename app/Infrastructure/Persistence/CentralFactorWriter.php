<?php

namespace App\Infrastructure\Persistence;

use App\Application\Contracts\CandidateDraftReader;
use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Candidate\SourceNormalizationRunResult;
use App\Infrastructure\Sources\Ademe\AdemeAdminReferenceMapper;
use Illuminate\Database\Connection;
use Illuminate\Database\DatabaseManager;
use Illuminate\Support\Collection;
use Illuminate\Support\Str;
use RuntimeException;

class CentralFactorWriter
{
    public function __construct(
        private DatabaseManager $databases,
        private CandidateDraftReader $reader,
        private AdemeAdminReferenceMapper $mapper,
    ) {}

    public function ensureAvailable(): void
    {
        $db = $this->databases->connection('central');
        foreach (['atlas_factor_imports', 'atlas_factor_records'] as $table) {
            if (! $db->getSchemaBuilder()->hasTable($table)) {
                throw new RuntimeException('Admin incoming-factor schema has not been applied.');
            }
        }
    }

    public function supports(string $source): bool
    {
        return $source === $this->mapper->sourceCode();
    }

    /** @return array{import_id: string, record_count: int, already_existed: bool} */
    public function write(SourceNormalizationRunResult $result): array
    {
        if (! $this->supports($result->input->sourceCode)) {
            throw new RuntimeException('This source does not have an Admin reference mapper yet.');
        }
        $this->ensureAvailable();
        $db = $this->databases->connection('central');
        $identity = hash('sha256', implode('|', [$result->input->sourceCode, $result->input->datasetId,
            $result->input->releaseVersion, $result->input->rawAssetSha256]));
        $source = ['provider' => $result->input->sourceCode, 'dataset' => $result->input->datasetId,
            'version' => $result->input->releaseVersion, 'artifact_sha256' => $result->input->rawAssetSha256];

        return $db->transaction(function () use ($db, $result, $identity, $source): array {
            $db->select('SELECT pg_advisory_xact_lock(hashtextextended(?, 0))', ['atlas-factor:'.$identity]);
            $existing = $db->table('atlas_factor_imports')
                ->where('source_code', $result->input->sourceCode)
                ->where('dataset_key', $result->input->datasetId)
                ->where('source_version', $result->input->releaseVersion)
                ->where('input_sha256', $result->input->rawAssetSha256)
                ->orderBy('created_at')->orderBy('id')->lockForUpdate()->first();
            $this->mapper->loadReferences($db);
            if ($existing !== null) {
                if ($existing->completed_at === null) {
                    throw new RuntimeException('An incomplete import exists for this identity.');
                }
                if ((int) $existing->record_count !== $result->normalizedArtifact->candidateCount) {
                    throw new RuntimeException('The same source file produced a different factor count; existing records were preserved.');
                }

                $this->refreshReferences($db, $existing->id, $source);

                return ['import_id' => $existing->id, 'record_count' => (int) $existing->record_count, 'already_existed' => true];
            }
            $id = (string) Str::uuid7();
            $now = now();
            $db->table('atlas_factor_imports')->insert([
                'id' => $id, 'source_code' => $result->input->sourceCode, 'dataset_key' => $result->input->datasetId,
                'source_version' => $result->input->releaseVersion, 'input_sha256' => $result->input->rawAssetSha256,
                'import_key' => $identity, 'record_count' => 0, 'source_published_at' => $result->input->sourcePublishedAt,
                'retrieved_at' => $result->input->retrievedAt, 'completed_at' => null, 'created_at' => $now, 'updated_at' => $now,
            ]);
            $count = 0;
            $batch = [];
            foreach ($this->reader->read($result->normalizedArtifact) as $draft) {
                $batch[] = $draft;
                if (count($batch) === 200) {
                    $count += $this->insertBatch($db, $id, $result->input->parsedArtifactId, $batch, $source);
                    $batch = [];
                }
            }
            $count += $this->insertBatch($db, $id, $result->input->parsedArtifactId, $batch, $source);
            if ($count < 1 || $count !== $result->normalizedArtifact->candidateCount) {
                throw new RuntimeException('Central factor count does not match the normalized source.');
            }
            $db->table('atlas_factor_imports')->where('id', $id)->update([
                'record_count' => $count, 'completed_at' => now(), 'updated_at' => now(),
            ]);

            return ['import_id' => $id, 'record_count' => $count, 'already_existed' => false];
        });
    }

    /** @param array<string, string> $source */
    private function refreshReferences(Connection $db, string $importId, array $source): void
    {
        $db->table('atlas_factor_records')->where('atlas_factor_import_id', $importId)
            ->select(['id', 'source_unit', 'value', 'payload', 'unit_match', 'geography_match', 'needs_attention'])
            ->chunkById(200, function (Collection $records) use ($db, $source): void {
                foreach ($records as $record) {
                    $payload = json_decode($record->payload, true, 512, JSON_THROW_ON_ERROR);
                    $unit = $this->mapper->unit($record->source_unit);
                    $geography = $this->mapper->geography($payload['source_rows'][0]['fields']);
                    $science = $this->mapper->science($payload);
                    $sourceScience = $this->mapper->sourceScience($payload, $record->source_unit, $record->value, $source);
                    $needsAttention = $unit['status'] !== 'matched' || $geography['status'] !== 'matched' || $record->value === null;
                    if (json_decode($record->unit_match, true, 512, JSON_THROW_ON_ERROR) == $unit
                        && json_decode($record->geography_match, true, 512, JSON_THROW_ON_ERROR) == $geography
                        && (bool) $record->needs_attention === $needsAttention
                        && ($payload['scientific_interpretation'] ?? null) == $science
                        && ($payload['source_science'] ?? null) == $sourceScience) {
                        continue;
                    }
                    $payload['scientific_interpretation'] = $science;
                    $payload['source_science'] = $sourceScience;
                    $db->table('atlas_factor_records')->where('id', $record->id)->update([
                        'unit_match' => json_encode($unit, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE),
                        'geography_match' => json_encode($geography, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE),
                        'needs_attention' => $needsAttention,
                        'payload' => json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE),
                    ]);
                }
            });
    }

    /** @param list<CandidateEntityDraft> $drafts @param array<string, string> $source */
    private function insertBatch(Connection $db, string $importId, string $parsedArtifactId, array $drafts, array $source): int
    {
        if ($drafts === []) {
            return 0;
        }
        $sourceRows = [];
        foreach ($drafts as $draft) {
            foreach ($draft->provenance as $provenance) {
                $sourceRows[] = $provenance['locator']['row'];
            }
        }
        $raw = $this->databases->connection()->table('parsed_observations')
            ->where('parsed_artifact_id', $parsedArtifactId)->whereIn('source_row', array_unique($sourceRows))
            ->get(['source_row', 'source_record_id', 'record_type', 'fields'])->keyBy('source_row');
        $rows = [];
        foreach ($drafts as $draft) {
            $primaryRow = $raw->get($draft->provenance[0]['locator']['row']);
            if ($primaryRow === null) {
                throw new RuntimeException('The source row of a factor is missing.');
            }
            $fields = json_decode($primaryRow->fields, true, 512, JSON_THROW_ON_ERROR);
            $sourceUnit = $draft->primaryQuantity['output_unit']['raw_label'] ?? null;
            $unit = $this->mapper->unit($sourceUnit);
            $geography = $this->mapper->geography($fields);
            $rawRows = [];
            foreach ($draft->provenance as $provenance) {
                $row = $raw->get($provenance['locator']['row']);
                if ($row === null) {
                    throw new RuntimeException('A component source row is missing.');
                }
                $rawRows[] = ['row' => (int) $row->source_row, 'type' => $row->record_type,
                    'fields' => json_decode($row->fields, true, 512, JSON_THROW_ON_ERROR)];
            }
            $payload = ['texts' => $draft->localizedTexts, 'components' => $draft->components,
                'temporal' => $draft->temporal, 'methodology' => $draft->methodology,
                'source_taxonomy' => $draft->sourceTaxonomy, 'source_rows' => $rawRows];
            $payload['scientific_interpretation'] = $this->mapper->science($payload);
            $payload['source_science'] = $this->mapper->sourceScience($payload, $sourceUnit, $draft->primaryQuantity['value'], $source);
            $rows[] = [
                'id' => (string) Str::uuid7(), 'atlas_factor_import_id' => $importId,
                'source_record_id' => $primaryRow->source_record_id,
                'logical_key' => $draft->logicalKey, 'variant_key' => $draft->variantKey,
                'name' => $draft->localizedTexts[0]['label'], 'value' => $draft->primaryQuantity['value'],
                'source_unit' => $sourceUnit, 'geography_label' => $draft->geographyProposals[0]['raw_label'] ?? null,
                'needs_attention' => $unit['status'] !== 'matched' || $geography['status'] !== 'matched' || $draft->primaryQuantity['value'] === null,
                'unit_match' => json_encode($unit, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE),
                'geography_match' => json_encode($geography, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE),
                'payload' => json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE),
                'created_at' => now(),
            ];
        }
        $db->table('atlas_factor_records')->insert($rows);

        return count($rows);
    }
}
