<?php

namespace App\Infrastructure\Sources\Ademe;

use App\Application\Contracts\SourceParsingAdapter;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use App\Domain\Ingestion\ParsedDataset;
use App\Domain\Ingestion\RawAssetToParse;
use JsonException;
use RuntimeException;
use Throwable;

final class AdemeCsvParser implements SourceParsingAdapter
{
    public const PARSER_VERSION = '1.0.0';

    public const SCHEMA_VERSION = 'ademe.base-carbone.v23.6';

    public const EXPECTED_HEADERS = [
        'Type Ligne',
        "Identifiant de l'élément",
        'Structure',
        "Type de l'élément",
        "Statut de l'élément",
        'Nom base français',
        'Nom base anglais',
        'Nom base espagnol',
        'Nom attribut français',
        'Nom attribut anglais',
        'Nom attribut espagnol',
        'Nom frontière français',
        'Nom frontière anglais',
        'Nom frontière espagnol',
        'Code de la catégorie',
        'Tags français',
        'Tags anglais',
        'Tags espagnol',
        'Unité français',
        'Unité anglais',
        'Unité espagnol',
        'Contributeur',
        'Autres Contributeurs',
        'Programme',
        'Url du programme',
        'Source',
        'Localisation géographique',
        'Sous-localisation géographique français',
        'Sous-localisation géographique anglais',
        'Sous-localisation géographique espagnol',
        'Date de création',
        'Date de modification',
        'Période de validité',
        'Incertitude',
        'Réglementations',
        'Transparence',
        'Qualité',
        'Qualité TeR',
        'Qualité GR',
        'Qualité TiR',
        'Qualité C',
        'Qualité P',
        'Qualité M',
        'Commentaire français',
        'Commentaire anglais',
        'Commentaire espagnol',
        'Type poste',
        'Nom poste français',
        'Nom poste anglais',
        'Nom poste espagnol',
        'Total poste non décomposé',
        'CO2f',
        'CH4f',
        'CH4b',
        'N2O',
        'Code gaz supplémentaire 1',
        'Valeur gaz supplémentaire 1',
        'Code gaz supplémentaire 2',
        'Valeur gaz supplémentaire 2',
        'Code gaz supplémentaire 3',
        'Valeur gaz supplémentaire 3',
        'Code gaz supplémentaire 4',
        'Valeur gaz supplémentaire 4',
        'Code gaz supplémentaire 5',
        'Valeur gaz supplémentaire 5',
        'Autres GES',
        'CO2b',
    ];

    private const DECIMAL_HEADERS = [
        'Incertitude',
        'Transparence',
        'Qualité',
        'Qualité TeR',
        'Qualité GR',
        'Qualité TiR',
        'Qualité C',
        'Qualité P',
        'Qualité M',
        'Total poste non décomposé',
        'CO2f',
        'CH4f',
        'CH4b',
        'N2O',
        'Valeur gaz supplémentaire 1',
        'Valeur gaz supplémentaire 2',
        'Valeur gaz supplémentaire 3',
        'Valeur gaz supplémentaire 4',
        'Valeur gaz supplémentaire 5',
        'Autres GES',
        'CO2b',
    ];

    private const REQUIRED_HEADERS = [
        'Type Ligne',
        "Identifiant de l'élément",
        'Structure',
        "Type de l'élément",
        "Statut de l'élément",
    ];

    private const VALID_FACTOR_STATUSES = [
        'Valide générique',
        'Valide spécifique',
    ];

    public function sourceCode(): string
    {
        return 'ADEME';
    }

    public function parserVersion(): string
    {
        return self::PARSER_VERSION;
    }

    /**
     * @param  resource  $stream
     */
    public function parse(mixed $stream, RawAssetToParse $rawAsset): ParsedDataset
    {
        if (! is_resource($stream)) {
            throw new SourceContractViolation('ADEME parser requires a readable raw stream.');
        }

        if ($rawAsset->sourceCode !== $this->sourceCode()) {
            throw new SourceContractViolation('ADEME parser received a foreign raw asset.');
        }

        $temporaryPath = tempnam(sys_get_temp_dir(), 'atlas-ademe-parsed-');

        if ($temporaryPath === false) {
            throw new RuntimeException('A temporary ADEME parsed artifact could not be created.');
        }

        $output = fopen($temporaryPath, 'wb');

        if ($output === false) {
            unlink($temporaryPath);

            throw new RuntimeException('The temporary ADEME parsed artifact could not be opened.');
        }

        try {
            [$headers, $sourceEncoding] = $this->readHeaders($stream);
            $metrics = [
                'exported_rows' => 0,
                'element_rows' => 0,
                'post_rows' => 0,
                'valid_factor_elements' => 0,
                'valid_factor_posts' => 0,
                'archived_rows' => 0,
                'source_data_rows' => 0,
            ];
            $validFactorElementRows = [];
            $recordNumber = 1;

            while (($rawFields = fgetcsv($stream, null, ';', '"', '')) !== false) {
                $recordNumber++;

                if ($this->isBlankRecord($rawFields)) {
                    continue;
                }

                if (count($rawFields) !== count($headers)) {
                    $direction = count($rawFields) > count($headers) ? 'excess' : 'missing';

                    throw new SourceContractViolation(
                        "ADEME Base Carbone has {$direction} columns at record {$recordNumber}.",
                    );
                }

                $fields = $this->convertFields($rawFields, $sourceEncoding, $recordNumber);
                /** @var array<string, string> $payload */
                $payload = array_combine($headers, $fields);
                $this->assertRequiredFields($payload, $recordNumber);
                $this->assertDecimals($payload, $recordNumber);

                $recordType = trim($payload['Type Ligne']);
                $sourceRecordId = trim($payload["Identifiant de l'élément"]);
                $elementType = trim($payload["Type de l'élément"]);
                $status = trim($payload["Statut de l'élément"]);
                $isValidFactor = $elementType === "Facteur d'émission"
                    && in_array($status, self::VALID_FACTOR_STATUSES, true);

                if ($recordType === 'Elément') {
                    $metrics['element_rows']++;
                } elseif ($recordType === 'Poste') {
                    $metrics['post_rows']++;
                }

                if ($isValidFactor && $recordType === 'Elément') {
                    if (isset($validFactorElementRows[$sourceRecordId])) {
                        $firstRow = $validFactorElementRows[$sourceRecordId];

                        throw new SourceContractViolation(
                            "ADEME Base Carbone duplicates valid factor element ID {$sourceRecordId} "
                            ."at records {$firstRow} and {$recordNumber}.",
                        );
                    }

                    $validFactorElementRows[$sourceRecordId] = $recordNumber;
                    $metrics['valid_factor_elements']++;
                }

                if ($isValidFactor && $recordType === 'Poste') {
                    $metrics['valid_factor_posts']++;
                }

                if ($status === 'Archivé') {
                    $metrics['archived_rows']++;
                }

                if ($elementType === 'Données source') {
                    $metrics['source_data_rows']++;
                }

                $fieldsJson = $this->encodeJson($payload);
                $observation = [
                    'source_row' => $recordNumber,
                    'record_type' => $recordType,
                    'source_record_id' => $sourceRecordId,
                    'element_type' => $elementType,
                    'status' => $status,
                    'row_sha256' => hash('sha256', $fieldsJson),
                    'fields' => $payload,
                ];

                if (fwrite($output, $this->encodeJson($observation)."\n") === false) {
                    throw new RuntimeException('ADEME parsed artifact could not be written.');
                }

                $metrics['exported_rows']++;
            }

            if ($metrics['exported_rows'] < 1) {
                throw new SourceContractViolation('ADEME Base Carbone export contains no records.');
            }

            if ($metrics['exported_rows'] !== $rawAsset->reportedRowCount) {
                throw new SourceContractViolation(
                    'ADEME Base Carbone row count changed: expected '
                    ."{$rawAsset->reportedRowCount}, parsed {$metrics['exported_rows']}.",
                );
            }
        } catch (Throwable $exception) {
            fclose($output);
            unlink($temporaryPath);

            throw $exception;
        }

        fclose($output);
        $fileSize = filesize($temporaryPath);
        $sha256 = hash_file('sha256', $temporaryPath);

        if (! is_int($fileSize) || ! is_string($sha256)) {
            unlink($temporaryPath);

            throw new RuntimeException('ADEME parsed artifact identity could not be calculated.');
        }

        return new ParsedDataset(
            temporaryPath: $temporaryPath,
            format: 'ndjson',
            parserVersion: self::PARSER_VERSION,
            schemaVersion: self::SCHEMA_VERSION,
            schemaSha256: self::schemaSha256(),
            sourceEncoding: $sourceEncoding,
            rowCount: $metrics['exported_rows'],
            fileSize: $fileSize,
            sha256: $sha256,
            metrics: $metrics,
        );
    }

    public static function schemaSha256(): string
    {
        return hash('sha256', implode("\x1F", self::EXPECTED_HEADERS));
    }

    /**
     * @param  resource  $stream
     * @return array{0: list<string>, 1: string}
     */
    private function readHeaders(mixed $stream): array
    {
        $rawHeaders = fgetcsv($stream, null, ';', '"', '');

        if (! is_array($rawHeaders) || $rawHeaders === []) {
            throw new SourceContractViolation('ADEME Base Carbone header is missing.');
        }

        $rawHeaders[0] = $this->stripUtf8Bom((string) $rawHeaders[0]);
        $sourceEncoding = $this->detectSourceEncoding($rawHeaders);
        $headers = $this->convertFields($rawHeaders, $sourceEncoding, 1);

        if ($headers !== self::EXPECTED_HEADERS) {
            throw new SourceContractViolation(
                'ADEME Base Carbone schema changed; parser and schema versions must be updated.',
            );
        }

        return [$headers, $sourceEncoding];
    }

    /**
     * @param  list<string|null>  $fields
     */
    private function detectSourceEncoding(array $fields): string
    {
        foreach ($fields as $field) {
            if (! mb_check_encoding((string) $field, 'UTF-8')) {
                return 'Windows-1252';
            }
        }

        return 'UTF-8';
    }

    /**
     * @param  list<string|null>  $fields
     * @return list<string>
     */
    private function convertFields(array $fields, string $sourceEncoding, int $recordNumber): array
    {
        $converted = [];

        foreach ($fields as $field) {
            $value = (string) $field;

            if ($sourceEncoding === 'UTF-8') {
                if (! mb_check_encoding($value, 'UTF-8')) {
                    throw new SourceContractViolation(
                        "ADEME Base Carbone contains invalid UTF-8 at record {$recordNumber}.",
                    );
                }

                $converted[] = $value;

                continue;
            }

            $converted[] = mb_convert_encoding($value, 'UTF-8', 'Windows-1252');
        }

        return $converted;
    }

    /**
     * @param  array<string, string>  $payload
     */
    private function assertRequiredFields(array $payload, int $recordNumber): void
    {
        foreach (self::REQUIRED_HEADERS as $header) {
            if (trim($payload[$header]) === '') {
                throw new SourceContractViolation(
                    "ADEME Base Carbone {$header} is missing at record {$recordNumber}.",
                );
            }
        }
    }

    /**
     * @param  array<string, string>  $payload
     */
    private function assertDecimals(array $payload, int $recordNumber): void
    {
        foreach (self::DECIMAL_HEADERS as $header) {
            $value = trim($payload[$header]);

            if ($value === '') {
                continue;
            }

            $normalized = preg_replace('/[\s\x{00A0}\x{202F}]+/u', '', $value);

            if (! is_string($normalized)) {
                throw new SourceContractViolation(
                    "ADEME Base Carbone {$header} could not be read at record {$recordNumber}.",
                );
            }

            $normalized = str_replace(',', '.', $normalized);

            if (preg_match('/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/D', $normalized) !== 1) {
                throw new SourceContractViolation(
                    "ADEME Base Carbone {$header} contains an invalid decimal at record {$recordNumber}: {$value}",
                );
            }
        }
    }

    /**
     * @param  list<string|null>  $fields
     */
    private function isBlankRecord(array $fields): bool
    {
        foreach ($fields as $field) {
            if (trim((string) $field) !== '') {
                return false;
            }
        }

        return true;
    }

    private function stripUtf8Bom(string $value): string
    {
        return str_starts_with($value, "\xEF\xBB\xBF") ? substr($value, 3) : $value;
    }

    /**
     * @param  array<array-key, mixed>  $payload
     *
     * @throws JsonException
     */
    private function encodeJson(array $payload): string
    {
        return json_encode(
            $payload,
            JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
        );
    }
}
