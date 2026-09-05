<?php

namespace Tests\Unit\Infrastructure\Candidate;

use App\Application\Candidate\BuildCanonicalCandidateEntity;
use App\Application\Contracts\CandidateEntityReader;
use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use Tests\Support\CandidateFixture;
use Tests\TestCase;

final class VerifiedCandidateEntityReaderTest extends TestCase
{
    public function test_reads_a_schema_valid_canonical_entity_with_verified_record_hash(): void
    {
        $entity = app(BuildCanonicalCandidateEntity::class)->handle(CandidateFixture::draft());
        $path = tempnam(sys_get_temp_dir(), 'atlas-reader-test-');
        $bytes = $entity->canonicalJson."\n";
        file_put_contents($path, $bytes);
        try {
            $member = new CandidateArchiveMember('entities.ndjson', $path, hash('sha256', $bytes), strlen($bytes), 1);
            $read = iterator_to_array(app(CandidateEntityReader::class)->read($member));
            $this->assertSame($entity->recordSha256, $read[0]->recordSha256);
        } finally {
            unlink($path);
        }
    }

    public function test_rejects_tampered_bytes_even_when_member_hash_is_recomputed(): void
    {
        $entity = app(BuildCanonicalCandidateEntity::class)->handle(CandidateFixture::draft());
        $bytes = str_replace('1.25', '9.25', $entity->canonicalJson)."\n";
        $path = tempnam(sys_get_temp_dir(), 'atlas-reader-test-');
        file_put_contents($path, $bytes);
        try {
            $member = new CandidateArchiveMember('entities.ndjson', $path, hash('sha256', $bytes), strlen($bytes), 1);
            $this->expectException(CandidateContractViolation::class);
            $this->expectExceptionMessage('record checksum');
            iterator_to_array(app(CandidateEntityReader::class)->read($member));
        } finally {
            unlink($path);
        }
    }
}
