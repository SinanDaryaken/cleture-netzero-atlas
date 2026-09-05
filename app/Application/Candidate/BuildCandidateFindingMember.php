<?php

namespace App\Application\Candidate;

use App\Application\Contracts\CandidateContractRegistry;
use App\Application\Contracts\CandidateRecordMemberWriter;
use App\Application\Contracts\CanonicalJson;
use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\CandidateRecordMember;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Candidate\NormalizationFinding;

final readonly class BuildCandidateFindingMember
{
    public function __construct(
        private CandidateContractRegistry $contracts,
        private CandidateRecordMemberWriter $writer,
        private CanonicalJson $canonicalJson,
    ) {}

    /** @param iterable<NormalizationFinding> $findings */
    public function handle(iterable $findings): CandidateArchiveMember
    {
        $schemaVersion = $this->contracts->get(CandidateContract::FindingRecord)->version;

        return $this->writer->write(
            CandidateRecordMember::Findings,
            $this->records($findings, $schemaVersion),
        );
    }

    /**
     * @param  iterable<NormalizationFinding>  $findings
     * @return \Generator<int, array<string, mixed>>
     */
    private function records(iterable $findings, string $schemaVersion): \Generator
    {
        foreach ($findings as $finding) {
            if (! $finding instanceof NormalizationFinding) {
                throw new CandidateContractViolation('Finding member received an invalid finding.');
            }

            $payload = [
                'schema_version' => $schemaVersion,
                'candidate_key' => $finding->candidateKey,
                'code' => $finding->code,
                'severity' => $finding->severity,
                'json_pointer' => null,
                'message' => $finding->message,
                'evidence_refs' => [],
                'context' => (object) $finding->context,
            ];

            yield [
                'schema_version' => $schemaVersion,
                'finding_key' => 'finding:'.hash('sha256', $this->canonicalJson->encode($payload)),
                ...array_slice($payload, 1, preserve_keys: true),
            ];
        }
    }
}
