<?php

namespace App\Infrastructure\Candidate;

use App\Application\Contracts\CandidateEntityReader;
use App\Application\Contracts\CandidateSchemaValidator;
use App\Application\Contracts\CanonicalJson;
use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\CanonicalCandidateEntity;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;

final readonly class VerifiedCandidateEntityReader implements CandidateEntityReader
{
    public function __construct(private CandidateSchemaValidator $schemas, private CanonicalJson $json) {}

    public function read(CandidateArchiveMember $member): iterable
    {
        if ($member->path !== 'entities.ndjson') {
            throw new CandidateContractViolation('Entity reader requires an entity member.');
        }
        $stream = fopen($member->temporaryPath, 'rb');
        if ($stream === false) {
            throw new CandidateContractViolation('Entity member could not be opened.');
        }
        $hash = hash_init('sha256');
        $count = $size = 0;
        try {
            while (($line = fgets($stream, 10 * 1024 * 1024 + 1)) !== false) {
                if (! str_ends_with($line, "\n")) {
                    throw new CandidateContractViolation('Entity NDJSON line exceeds the limit or lacks its terminator.');
                }
                $size += strlen($line);
                hash_update($hash, $line);
                $object = json_decode($line, false, 512, JSON_THROW_ON_ERROR);
                if (! $object instanceof \stdClass) {
                    throw new CandidateContractViolation('Entity NDJSON line must be an object.');
                }
                $record = json_decode($line, true, 512, JSON_THROW_ON_ERROR);
                $this->schemas->assertValid(CandidateContract::EntityRecord, get_object_vars($object));
                $sha256 = $object->record_sha256;
                unset($object->record_sha256);
                if (! hash_equals($sha256, hash('sha256', $this->json->encode($object)))) {
                    throw new CandidateContractViolation('Entity record checksum does not match.');
                }
                $object->record_sha256 = $sha256;
                $canonical = $this->json->encode($object);
                if ($line !== $canonical."\n") {
                    throw new CandidateContractViolation('Entity member is not canonical NDJSON.');
                }
                $count++;
                yield new CanonicalCandidateEntity($record['candidate_key'], $sha256, $record, $canonical);
            }
            if (! feof($stream) || $count !== $member->recordCount || $size !== $member->sizeBytes || ! hash_equals($member->sha256, hash_final($hash))) {
                throw new CandidateContractViolation('Entity member identity does not match after reading.');
            }
        } finally {
            fclose($stream);
        }
    }
}
