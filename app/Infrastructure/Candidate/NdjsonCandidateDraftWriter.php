<?php

namespace App\Infrastructure\Candidate;

use App\Application\Contracts\CandidateDraftWriter;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\CandidateContractDocument;
use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Candidate\NormalizedCandidateDataset;
use App\Domain\Candidate\SourceNormalizationResult;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use JsonException;
use RuntimeException;
use Throwable;

final readonly class NdjsonCandidateDraftWriter implements CandidateDraftWriter
{
    public function write(
        SourceNormalizationResult $result,
        string $normalizerVersion,
        CandidateContractDocument $entityContract,
    ): NormalizedCandidateDataset {
        if ($entityContract->contract !== CandidateContract::EntityRecord) {
            throw new SourceContractViolation('Candidate draft writer requires the entity record contract.');
        }

        $temporaryPath = tempnam(sys_get_temp_dir(), 'atlas-candidate-draft-');

        if ($temporaryPath === false) {
            throw new RuntimeException('A temporary candidate draft artifact could not be created.');
        }

        $output = fopen($temporaryPath, 'wb');

        if ($output === false) {
            unlink($temporaryPath);

            throw new RuntimeException('The temporary candidate draft artifact could not be opened.');
        }

        $candidateCount = 0;

        try {
            foreach ($result->candidates as $candidate) {
                if (! $candidate instanceof CandidateEntityDraft) {
                    throw new SourceContractViolation('Normalization produced an invalid candidate entity draft.');
                }

                $line = $this->encode($candidate->toUnhashedRecord())."\n";

                if (fwrite($output, $line) !== strlen($line)) {
                    throw new RuntimeException('Candidate draft artifact could not be written.');
                }

                $candidateCount++;
            }
        } catch (Throwable $exception) {
            fclose($output);
            unlink($temporaryPath);

            throw $exception;
        }

        if ($candidateCount < 1) {
            fclose($output);
            unlink($temporaryPath);

            throw new SourceContractViolation('Normalization produced no candidate entities.');
        }

        if (($result->metrics['candidate_entities'] ?? null) !== $candidateCount) {
            fclose($output);
            unlink($temporaryPath);

            throw new SourceContractViolation('Normalization candidate count does not match its metrics.');
        }

        fclose($output);
        $fileSize = filesize($temporaryPath);
        $sha256 = hash_file('sha256', $temporaryPath);

        if (! is_int($fileSize) || ! is_string($sha256)) {
            unlink($temporaryPath);

            throw new RuntimeException('Candidate draft artifact identity could not be calculated.');
        }

        return new NormalizedCandidateDataset(
            temporaryPath: $temporaryPath,
            format: 'ndjson',
            normalizerVersion: $normalizerVersion,
            candidateSchemaVersion: $entityContract->version,
            candidateSchemaSha256: $entityContract->sha256,
            candidateCount: $candidateCount,
            findingCount: count($result->findings),
            fileSize: $fileSize,
            sha256: $sha256,
            findings: $result->findings,
            metrics: $result->metrics,
        );
    }

    /** @param array<string, mixed> $record */
    private function encode(array $record): string
    {
        try {
            return json_encode(
                $record,
                JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE,
            );
        } catch (JsonException $exception) {
            throw new SourceContractViolation('Candidate draft could not be encoded.', previous: $exception);
        }
    }
}
