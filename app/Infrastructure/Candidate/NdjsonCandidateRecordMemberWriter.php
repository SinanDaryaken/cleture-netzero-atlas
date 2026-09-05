<?php

namespace App\Infrastructure\Candidate;

use App\Application\Contracts\CandidateRecordMemberWriter;
use App\Application\Contracts\CandidateSchemaValidator;
use App\Application\Contracts\CanonicalJson;
use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CandidateRecordMember;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use RuntimeException;
use Throwable;

final readonly class NdjsonCandidateRecordMemberWriter implements CandidateRecordMemberWriter
{
    public function __construct(
        private CanonicalJson $canonicalJson,
        private CandidateSchemaValidator $schemaValidator,
    ) {}

    public function write(CandidateRecordMember $member, iterable $records): CandidateArchiveMember
    {
        $temporaryPath = tempnam(sys_get_temp_dir(), 'atlas-v2-member-');

        if ($temporaryPath === false) {
            throw new RuntimeException("A temporary {$member->value} member could not be created.");
        }

        $output = fopen($temporaryPath, 'wb');

        if ($output === false) {
            unlink($temporaryPath);

            throw new RuntimeException("The temporary {$member->value} member could not be opened.");
        }

        $identities = [];
        $recordCount = 0;

        try {
            foreach ($records as $record) {
                if (! is_array($record)) {
                    throw new CandidateContractViolation("{$member->value} received an invalid record.");
                }

                $identity = $record[$member->identityField()] ?? null;

                if (! is_string($identity) || $identity === '') {
                    throw new CandidateContractViolation("{$member->value} record identity is invalid.");
                }

                if (isset($identities[$identity])) {
                    throw new CandidateContractViolation("Duplicate {$member->identityField()} {$identity}.");
                }

                $this->schemaValidator->assertValid($member->contract(), $record);
                $line = $this->canonicalJson->encode($record)."\n";

                if (fwrite($output, $line) !== strlen($line)) {
                    throw new RuntimeException("{$member->value} could not be written completely.");
                }

                $identities[$identity] = true;
                $recordCount++;
            }
        } catch (Throwable $exception) {
            fclose($output);
            unlink($temporaryPath);

            throw $exception;
        }

        fclose($output);
        $sizeBytes = filesize($temporaryPath);
        $sha256 = hash_file('sha256', $temporaryPath);

        if (! is_int($sizeBytes) || ! is_string($sha256)) {
            unlink($temporaryPath);

            throw new RuntimeException("{$member->value} identity could not be calculated.");
        }

        return new CandidateArchiveMember(
            path: $member->value,
            temporaryPath: $temporaryPath,
            sha256: $sha256,
            sizeBytes: $sizeBytes,
            recordCount: $recordCount,
        );
    }
}
