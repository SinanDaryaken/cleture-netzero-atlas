<?php

namespace Tests\Unit\Infrastructure\Sources\Ademe;

use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use App\Domain\Ingestion\RawAssetToParse;
use App\Infrastructure\Sources\Ademe\AdemeCsvParser;
use Tests\TestCase;

final class AdemeCsvParserTest extends TestCase
{
    public function test_preserves_all_record_types_and_cp1252_field_values(): void
    {
        $rows = [
            $this->row([
                "Identifiant de l'élément" => '100',
                'Nom base français' => 'Électricité réseau',
                'Total poste non décomposé' => '1,25',
            ]),
            $this->row([
                'Type Ligne' => 'Poste',
                "Identifiant de l'élément" => '100',
                'Total poste non décomposé' => '0,25',
            ]),
            $this->row([
                "Identifiant de l'élément" => '200',
                "Statut de l'élément" => 'Archivé',
            ]),
            $this->row([
                "Identifiant de l'élément" => '300',
                "Type de l'élément" => 'Données source',
            ]),
        ];
        $stream = $this->csvStream($rows, 'Windows-1252');

        $dataset = (new AdemeCsvParser)->parse($stream, $this->rawAsset(4));

        fclose($stream);
        $observations = $this->observations($dataset->temporaryPath);
        unlink($dataset->temporaryPath);
        $this->assertSame('Windows-1252', $dataset->sourceEncoding);
        $this->assertSame(4, $dataset->rowCount);
        $this->assertSame([
            'exported_rows' => 4,
            'element_rows' => 3,
            'post_rows' => 1,
            'valid_factor_elements' => 1,
            'valid_factor_posts' => 1,
            'archived_rows' => 1,
            'source_data_rows' => 1,
        ], $dataset->metrics);
        $this->assertSame('Électricité réseau', $observations[0]['fields']['Nom base français']);
        $this->assertSame('1,25', $observations[0]['fields']['Total poste non décomposé']);
        $this->assertSame('Poste', $observations[1]['record_type']);
    }

    public function test_accepts_a_utf8_bom_without_changing_the_schema(): void
    {
        $stream = $this->csvStream([$this->row()], 'UTF-8', true);

        $dataset = (new AdemeCsvParser)->parse($stream, $this->rawAsset(1));

        fclose($stream);
        unlink($dataset->temporaryPath);
        $this->assertSame('UTF-8', $dataset->sourceEncoding);
        $this->assertSame(AdemeCsvParser::schemaSha256(), $dataset->schemaSha256);
    }

    public function test_rejects_schema_drift_with_an_extra_column(): void
    {
        $headers = [...AdemeCsvParser::EXPECTED_HEADERS, 'Unexpected'];
        $row = [...array_values($this->row()), 'value'];
        $stream = $this->rawCsvStream($headers, [$row]);

        try {
            (new AdemeCsvParser)->parse($stream, $this->rawAsset(1));
            $this->fail('Schema drift was not rejected.');
        } catch (SourceContractViolation $exception) {
            $this->assertSame(
                'ADEME Base Carbone schema changed; parser and schema versions must be updated.',
                $exception->getMessage(),
            );
        } finally {
            fclose($stream);
        }
    }

    public function test_rejects_a_data_record_with_excess_columns(): void
    {
        $row = [...array_values($this->row()), 'unexpected'];
        $stream = $this->rawCsvStream(AdemeCsvParser::EXPECTED_HEADERS, [$row]);

        try {
            (new AdemeCsvParser)->parse($stream, $this->rawAsset(1));
            $this->fail('Excess record columns were not rejected.');
        } catch (SourceContractViolation $exception) {
            $this->assertSame(
                'ADEME Base Carbone has excess columns at record 2.',
                $exception->getMessage(),
            );
        } finally {
            fclose($stream);
        }
    }

    public function test_rejects_an_invalid_decimal(): void
    {
        $stream = $this->csvStream([
            $this->row(['Total poste non décomposé' => 'not-a-decimal']),
        ]);

        try {
            (new AdemeCsvParser)->parse($stream, $this->rawAsset(1));
            $this->fail('Invalid decimal was not rejected.');
        } catch (SourceContractViolation $exception) {
            $this->assertStringContainsString('contains an invalid decimal at record 2', $exception->getMessage());
        } finally {
            fclose($stream);
        }
    }

    public function test_rejects_duplicate_valid_factor_element_ids(): void
    {
        $stream = $this->csvStream([
            $this->row(["Identifiant de l'élément" => 'duplicate']),
            $this->row(["Identifiant de l'élément" => 'duplicate']),
        ]);

        try {
            (new AdemeCsvParser)->parse($stream, $this->rawAsset(2));
            $this->fail('Duplicate valid factor ID was not rejected.');
        } catch (SourceContractViolation $exception) {
            $this->assertSame(
                'ADEME Base Carbone duplicates valid factor element ID duplicate at records 2 and 3.',
                $exception->getMessage(),
            );
        } finally {
            fclose($stream);
        }
    }

    public function test_rejects_a_row_count_that_differs_from_release_metadata(): void
    {
        $stream = $this->csvStream([$this->row()]);

        try {
            (new AdemeCsvParser)->parse($stream, $this->rawAsset(2));
            $this->fail('Row count drift was not rejected.');
        } catch (SourceContractViolation $exception) {
            $this->assertSame(
                'ADEME Base Carbone row count changed: expected 2, parsed 1.',
                $exception->getMessage(),
            );
        } finally {
            fclose($stream);
        }
    }

    /**
     * @param  array<string, string>  $overrides
     * @return array<string, string>
     */
    private function row(array $overrides = []): array
    {
        return array_replace(array_fill_keys(AdemeCsvParser::EXPECTED_HEADERS, ''), [
            'Type Ligne' => 'Elément',
            "Identifiant de l'élément" => '100',
            'Structure' => 'élément non décomposé',
            "Type de l'élément" => "Facteur d'émission",
            "Statut de l'élément" => 'Valide générique',
        ], $overrides);
    }

    /**
     * @param  list<array<string, string>>  $rows
     * @return resource
     */
    private function csvStream(
        array $rows,
        string $encoding = 'UTF-8',
        bool $withBom = false,
    ): mixed {
        return $this->rawCsvStream(
            AdemeCsvParser::EXPECTED_HEADERS,
            array_map('array_values', $rows),
            $encoding,
            $withBom,
        );
    }

    /**
     * @param  list<string>  $headers
     * @param  list<list<string>>  $rows
     * @return resource
     */
    private function rawCsvStream(
        array $headers,
        array $rows,
        string $encoding = 'UTF-8',
        bool $withBom = false,
    ): mixed {
        $csv = fopen('php://temp', 'w+b');
        $stream = fopen('php://temp', 'w+b');

        if (! is_resource($csv) || ! is_resource($stream)) {
            $this->fail('Temporary CSV stream could not be created.');
        }

        fputcsv($csv, $headers, ';', '"', '');

        foreach ($rows as $row) {
            fputcsv($csv, $row, ';', '"', '');
        }

        rewind($csv);
        $content = stream_get_contents($csv);
        fclose($csv);

        if ($encoding !== 'UTF-8') {
            $content = mb_convert_encoding($content, $encoding, 'UTF-8');
        } elseif ($withBom) {
            $content = "\xEF\xBB\xBF".$content;
        }

        fwrite($stream, $content);
        rewind($stream);

        return $stream;
    }

    private function rawAsset(int $reportedRowCount): RawAssetToParse
    {
        return new RawAssetToParse(
            sourceCode: 'ADEME',
            releaseVersion: '23.6',
            releaseRevisionSha256: str_repeat('a', 64),
            reportedRowCount: $reportedRowCount,
            rawAssetId: '01991a75-caa5-72ef-88d0-bdb732624a14',
            disk: 'atlas_raw',
            objectKey: 'sources/ademe/test.csv',
            fileSize: 1,
            sha256: str_repeat('b', 64),
        );
    }

    /**
     * @return list<array<string, mixed>>
     */
    private function observations(string $path): array
    {
        $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);

        if (! is_array($lines)) {
            $this->fail('Parsed observations could not be read.');
        }

        return array_map(
            fn (string $line): array => json_decode($line, true, flags: JSON_THROW_ON_ERROR),
            $lines,
        );
    }
}
