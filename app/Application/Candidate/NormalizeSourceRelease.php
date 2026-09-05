<?php

namespace App\Application\Candidate;

use App\Application\Contracts\CandidateContractRegistry;
use App\Application\Contracts\CandidateDraftWriter;
use App\Application\Contracts\NormalizationLedger;
use App\Application\Contracts\NormalizedArtifactStorage;
use App\Application\Contracts\ParsedObservationReader;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\NormalizedCandidateDataset;
use App\Domain\Candidate\SourceNormalizationRunResult;
use Throwable;

final readonly class NormalizeSourceRelease
{
    public function __construct(
        private SourceNormalizerRegistry $normalizers,
        private CandidateContractRegistry $contracts,
        private NormalizationLedger $ledger,
        private ParsedObservationReader $observations,
        private CandidateDraftWriter $writer,
        private NormalizedArtifactStorage $storage,
    ) {}

    public function handle(string $sourceCode): SourceNormalizationRunResult
    {
        $normalizer = $this->normalizers->for($sourceCode);
        $entityContract = $this->contracts->get(CandidateContract::EntityRecord);
        $attempt = $this->ledger->beginNormalization(
            sourceCode: $normalizer->sourceCode(),
            normalizerVersion: $normalizer->normalizerVersion(),
            candidateSchemaVersion: $entityContract->version,
            candidateSchemaSha256: $entityContract->sha256,
        );

        if ($attempt->existingArtifact !== null) {
            return new SourceNormalizationRunResult($attempt->input, $attempt->existingArtifact);
        }

        $dataset = null;

        try {
            $result = $normalizer->normalize(
                $this->observations->read($attempt->input),
                $attempt->input->context($entityContract->version),
            );
            $dataset = $this->writer->write(
                result: $result,
                normalizerVersion: $normalizer->normalizerVersion(),
                entityContract: $entityContract,
            );
            $artifact = $this->storage->store($attempt->input, $dataset);
            $this->ledger->completeNormalization($attempt, $dataset, $artifact);

            return new SourceNormalizationRunResult($attempt->input, $artifact);
        } catch (Throwable $exception) {
            $this->ledger->failNormalization($attempt, $exception);

            throw $exception;
        } finally {
            $this->removeTemporaryDataset($dataset);
        }
    }

    private function removeTemporaryDataset(?NormalizedCandidateDataset $dataset): void
    {
        if ($dataset !== null && is_file($dataset->temporaryPath)) {
            unlink($dataset->temporaryPath);
        }
    }
}
