<?php

namespace Tests\Feature;

use App\Application\Contracts\CandidateDraftReader;
use App\Domain\Candidate\ParsedArtifactToNormalize;
use App\Domain\Candidate\SourceNormalizationRunResult;
use App\Domain\Candidate\StoredNormalizedArtifact;
use App\Infrastructure\Persistence\CentralFactorWriter;
use App\Infrastructure\Sources\Ademe\AdemeAdminReferenceMapper;
use DateTimeImmutable;
use Illuminate\Database\DatabaseManager;
use Illuminate\Database\SQLiteConnection;
use Mockery;
use PDO;
use RuntimeException;
use Tests\TestCase;

class CentralFactorWriterTest extends TestCase
{
    private SQLiteConnection $central;

    private CentralFactorWriter $writer;

    protected function setUp(): void
    {
        parent::setUp();
        $this->central = Mockery::mock(SQLiteConnection::class.'[select]', [new PDO('sqlite::memory:')]);
        $this->central->shouldReceive('select')->passthru()->byDefault();
        $this->central->shouldReceive('select')->with('SELECT pg_advisory_xact_lock(hashtextextended(?, 0))', Mockery::type('array'))->andReturn([]);
        $this->central->statement('CREATE TABLE atlas_factor_imports (id TEXT PRIMARY KEY, source_code TEXT, dataset_key TEXT, source_version TEXT, input_sha256 TEXT, import_key TEXT UNIQUE, record_count INTEGER, source_published_at TEXT, retrieved_at TEXT, completed_at TEXT, created_at TEXT, updated_at TEXT, gwp_profile TEXT)');
        $this->central->statement('CREATE TABLE atlas_factor_records (id TEXT PRIMARY KEY, atlas_factor_import_id TEXT, source_unit TEXT, value TEXT, payload TEXT, unit_match TEXT, geography_match TEXT, needs_attention BOOLEAN, review_status TEXT, review_revision INTEGER, admin_references TEXT, reviewed_by TEXT, reviewed_at TEXT)');
        $this->central->table('atlas_factor_imports')->insert([
            'id' => 'original', 'source_code' => 'ADEME', 'dataset_key' => 'base-carboner', 'source_version' => '23.6',
            'input_sha256' => str_repeat('a', 64), 'import_key' => 'legacy-normalized-artifact-identity', 'record_count' => 1,
            'completed_at' => '2026-09-08 07:00:00', 'created_at' => '2026-09-08 07:00:00',
            'gwp_profile' => '{"assessment":"source owner metadata"}',
        ]);
        $this->central->table('atlas_factor_records')->insert([
            'id' => 'factor-original', 'atlas_factor_import_id' => 'original', 'source_unit' => 'kgCO2e/kWh', 'value' => '0.03200',
            'payload' => json_encode(['source_rows' => [['fields' => ['original' => 'source']]], 'components' => []]),
            'unit_match' => '{"status":"matched"}', 'geography_match' => '{"status":"matched"}', 'needs_attention' => false,
            'review_status' => 'approved', 'review_revision' => 3,
            'admin_references' => '{"unit_mode":"custom","unit_note":"Source condition"}',
            'reviewed_by' => 'admin-original', 'reviewed_at' => '2026-09-08 10:00:00',
        ]);
        $databases = Mockery::mock(DatabaseManager::class);
        $databases->shouldReceive('connection')->with('central')->andReturn($this->central);
        $reader = Mockery::mock(CandidateDraftReader::class);
        $reader->shouldReceive('read')->andThrow(new RuntimeException('New source input reached the reader.'));
        $mapper = Mockery::mock(AdemeAdminReferenceMapper::class);
        $mapper->shouldReceive('sourceCode')->andReturn('ADEME');
        $mapper->shouldReceive('loadReferences')->with($this->central);
        $mapper->shouldReceive('unit')->andReturn(['status' => 'matched']);
        $mapper->shouldReceive('geography')->andReturn(['status' => 'matched']);
        $mapper->shouldReceive('science')->andReturn(['schema_version' => 1, 'groups' => []]);
        $mapper->shouldReceive('sourceScience')->andReturn(['schema_version' => 1, 'gwp' => null]);
        $this->writer = new CentralFactorWriter($databases, $reader, $mapper);
    }

    private function input(string $revision = 'b', string $normalized = 'c', string $raw = 'a', string $version = '23.6', string $dataset = 'base-carboner', int $count = 1): SourceNormalizationRunResult
    {
        return new SourceNormalizationRunResult(
            new ParsedArtifactToNormalize('ADEME', $dataset, $version, str_repeat($revision, 64), 'parsed', 'local', 'parsed.ndjson', 1,
                str_repeat('d', 64), '1.0.0', 'raw.csv', str_repeat($raw, 64), new DateTimeImmutable('2026-09-08 11:00:00'), null),
            new StoredNormalizedArtifact('local', 'normalized.ndjson', 'ndjson', '1.0.0', 'v1', str_repeat('e', 64), $count, 0, 1, str_repeat($normalized, 64), false),
        );
    }

    public function test_refetch_and_changed_normalized_hash_reuse_legacy_import_preserving_profile_and_raw_values(): void
    {
        $before = $this->central->table('atlas_factor_imports')->first();
        foreach ([$this->input(), $this->input(revision: 'f', normalized: 'a')] as $result) {
            $written = $this->writer->write($result);
            $this->assertSame(['import_id' => 'original', 'record_count' => 1, 'already_existed' => true], $written);
        }
        $this->assertEquals($before, $this->central->table('atlas_factor_imports')->first());
        $this->assertSame(1, $this->central->table('atlas_factor_imports')->count());
        $this->assertSame(1, $this->central->table('atlas_factor_records')->count());
        $record = $this->central->table('atlas_factor_records')->first();
        $this->assertSame('factor-original', $record->id);
        $this->assertSame('0.03200', $record->value);
        $this->assertSame('approved', $record->review_status);
        $this->assertSame(3, $record->review_revision);
        $this->assertSame('{"unit_mode":"custom","unit_note":"Source condition"}', $record->admin_references);
        $this->assertSame('admin-original', $record->reviewed_by);
        $this->assertSame('2026-09-08 10:00:00', $record->reviewed_at);
        $payload = json_decode($record->payload, true);
        $this->assertSame('source', $payload['source_rows'][0]['fields']['original']);
        $this->assertSame(1, $payload['scientific_interpretation']['schema_version']);
        $this->assertSame(['schema_version' => 1, 'gwp' => null], $payload['source_science']);
    }

    public function test_different_source_file_version_or_dataset_is_not_treated_as_a_replay(): void
    {
        foreach ([$this->input(raw: 'b'), $this->input(version: '23.7'), $this->input(dataset: 'other')] as $result) {
            try {
                $this->writer->write($result);
                $this->fail('Different source identity must proceed to source reading.');
            } catch (RuntimeException $exception) {
                $this->assertSame('New source input reached the reader.', $exception->getMessage());
            }
            $this->assertSame(1, $this->central->table('atlas_factor_imports')->count());
        }
    }

    public function test_incomplete_import_and_changed_count_are_rejected_without_mutating_existing_records(): void
    {
        foreach ([false, true] as $incomplete) {
            if ($incomplete) {
                $this->central->table('atlas_factor_imports')->update(['completed_at' => null]);
            }
            try {
                $this->writer->write($this->input(count: $incomplete ? 1 : 2));
                $this->fail('Existing source data must not be replaced.');
            } catch (RuntimeException $exception) {
                $this->assertStringContainsString($incomplete ? 'incomplete import' : 'different factor count', $exception->getMessage());
            }
            $this->assertSame(1, $this->central->table('atlas_factor_records')->count());
            $this->assertArrayNotHasKey('scientific_interpretation', json_decode($this->central->table('atlas_factor_records')->value('payload'), true));
        }
    }
}
