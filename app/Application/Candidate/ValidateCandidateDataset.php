<?php

namespace App\Application\Candidate;

use App\Application\Contracts\CandidateEntityReader;
use App\Application\Contracts\CandidateValidationRulesetLoader;
use App\Application\Contracts\CanonicalJson;
use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CandidateSemanticValidation;
use App\Domain\Candidate\CandidateValidationReceipt;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Candidate\LicenseSnapshot;
use App\Domain\Candidate\ValidatedCandidateDataset;
use App\Domain\Catalog\CatalogSnapshot;

final readonly class ValidateCandidateDataset
{
    public function __construct(
        private CandidateEntityReader $entities,
        private CandidateValidationRulesetLoader $rulesets,
        private CandidateSemanticValidation $validation,
        private BuildCandidateFindingMember $findings,
        private CanonicalJson $json,
    ) {}

    public function handle(CandidateArchiveMember $entities, CatalogSnapshot $unit, CatalogSnapshot $geography, LicenseSnapshot $licenseSnapshot, array $rawAssets, string $normalizedArtifactId, iterable $normalizationFindings = []): ValidatedCandidateDataset
    {
        $license = $licenseSnapshot->license;
        $rules = $this->rulesets->load();
        $summary = ['clean' => 0, 'review_required' => 0, 'blocking' => 0, 'findings' => 0];
        $blocked = false;
        $records = function () use ($entities, $unit, $geography, $rawAssets, $rules, $normalizationFindings, &$summary, &$blocked): \Generator {
            $seen = $semantic = [];
            foreach ($this->entities->read($entities) as $entity) {
                $identity = $entity->record['logical_key']."\0".$entity->record['variant_key'];
                if (isset($seen[$entity->candidateKey]) || isset($semantic[$identity])) {
                    throw new CandidateContractViolation('Duplicate entity identity during validation.');
                }
                $seen[$entity->candidateKey] = 'clean';
                $semantic[$identity] = true;
                $findings = $this->validation->inspect($entity->record, $rules, $unit, $geography, $rawAssets['assets']);
                usort($findings, fn ($a, $b) => [$a->code, $a->jsonPointer] <=> [$b->code, $b->jsonPointer]);
                foreach ($findings as $finding) {
                    $blocked = $blocked || $rules->document['rules'][$finding->code]['package_block'];
                    $seen[$entity->candidateKey] = $this->disposition($seen[$entity->candidateKey], $finding->severity);
                    $summary['findings']++;
                    yield $finding;
                }
            }
            foreach ($normalizationFindings as $finding) {
                if (! isset($seen[$finding->candidateKey])) {
                    throw new CandidateContractViolation('Normalization finding references an unknown candidate.');
                }
                $seen[$finding->candidateKey] = $this->disposition($seen[$finding->candidateKey], $finding->severity);
                $summary['findings']++;
                yield $finding;
            }
            foreach ($seen as $disposition) {
                $summary[$disposition]++;
            }
        };
        $findings = $this->findings->handle($records());
        $catalogs = [
            'unit' => ['version' => $unit->descriptor->version, 'sha256' => $unit->descriptor->sha256],
            'geography' => ['owner' => 'NetZeroAdmin', 'version' => $geography->descriptor->version, 'sha256' => $geography->descriptor->sha256],
        ];
        $identity = hash('sha256', $this->json->encode([
            'normalized_artifact_id' => $normalizedArtifactId,
            'entities' => $entities->sha256, 'findings' => $findings->sha256, 'ruleset' => $rules->sha256,
            'catalogs' => $catalogs, 'license_descriptor' => $licenseSnapshot->descriptorSha256, 'license' => $license, 'raw_assets' => $rawAssets,
        ]));

        return new ValidatedCandidateDataset(new CandidateValidationReceipt(
            $identity, $entities->sha256, $findings->sha256, $rules->document['ruleset_version'], $rules->sha256,
            $catalogs, $license, $rawAssets, $entities->recordCount, $summary, $blocked,
        ), $findings);
    }

    private function disposition(string $current, string $severity): string
    {
        if ($current === 'blocking' || $severity === 'blocking') {
            return 'blocking';
        }

        return $severity === 'review' || $current === 'review_required' ? 'review_required' : 'clean';
    }
}
