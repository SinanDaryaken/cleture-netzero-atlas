<?php

namespace App\Infrastructure\Candidate;

use App\Application\Candidate\BuildV2CandidateEntity;
use App\Application\Contracts\CandidateEntityMemberWriter;
use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use RuntimeException;
use Throwable;

final readonly class NdjsonCandidateEntityMemberWriter implements CandidateEntityMemberWriter
{
    public function __construct(private BuildV2CandidateEntity $entities) {}

    public function write(iterable $drafts): CandidateArchiveMember
    {
        $temporaryPath = tempnam(sys_get_temp_dir(), 'atlas-v2-entities-');

        if ($temporaryPath === false) {
            throw new RuntimeException('A temporary V2 entity member could not be created.');
        }

        $output = fopen($temporaryPath, 'wb');

        if ($output === false) {
            unlink($temporaryPath);

            throw new RuntimeException('The temporary V2 entity member could not be opened.');
        }

        $candidateKeys = [];
        $semanticKeys = [];
        $recordCount = 0;

        try {
            foreach ($drafts as $draft) {
                if (! $draft instanceof CandidateEntityDraft) {
                    throw new CandidateContractViolation('V2 entity member received an invalid candidate draft.');
                }

                $entity = $this->entities->handle($draft);
                $semanticKey = $entity->record['logical_key']."\0".$entity->record['variant_key'];

                if (isset($candidateKeys[$entity->candidateKey])) {
                    throw new CandidateContractViolation("Duplicate candidate key {$entity->candidateKey}.");
                }

                if (isset($semanticKeys[$semanticKey])) {
                    throw new CandidateContractViolation('Duplicate logical and variant candidate identity.');
                }

                $line = $entity->canonicalJson."\n";

                if (fwrite($output, $line) !== strlen($line)) {
                    throw new RuntimeException('V2 entity member could not be written completely.');
                }

                $candidateKeys[$entity->candidateKey] = true;
                $semanticKeys[$semanticKey] = true;
                $recordCount++;
            }
        } catch (Throwable $exception) {
            fclose($output);
            unlink($temporaryPath);

            throw $exception;
        }

        fclose($output);

        if ($recordCount < 1) {
            unlink($temporaryPath);

            throw new CandidateContractViolation('V2 entity member cannot be empty.');
        }

        $sizeBytes = filesize($temporaryPath);
        $sha256 = hash_file('sha256', $temporaryPath);

        if (! is_int($sizeBytes) || ! is_string($sha256)) {
            unlink($temporaryPath);

            throw new RuntimeException('V2 entity member identity could not be calculated.');
        }

        return new CandidateArchiveMember(
            path: 'entities.ndjson',
            temporaryPath: $temporaryPath,
            sha256: $sha256,
            sizeBytes: $sizeBytes,
            recordCount: $recordCount,
        );
    }
}
