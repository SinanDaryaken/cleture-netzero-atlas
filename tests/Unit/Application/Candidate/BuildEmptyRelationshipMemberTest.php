<?php

namespace Tests\Unit\Application\Candidate;

use App\Application\Candidate\BuildEmptyRelationshipMember;
use Tests\TestCase;

final class BuildEmptyRelationshipMemberTest extends TestCase
{
    public function test_builds_the_required_zero_byte_v2_relationship_member(): void
    {
        $member = (new BuildEmptyRelationshipMember)->handle();

        try {
            $this->assertSame('relationships.ndjson', $member->path);
            $this->assertSame(0, $member->sizeBytes);
            $this->assertSame(0, $member->recordCount);
            $this->assertSame(
                'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
                $member->sha256,
            );
        } finally {
            unlink($member->temporaryPath);
        }
    }
}
