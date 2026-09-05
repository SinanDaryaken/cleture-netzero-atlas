<?php

namespace App\Infrastructure\Sources\Ademe;

use App\Application\Contracts\SourceNormalizationAdapter;
use App\Domain\Candidate\CandidateEntityDraft;
use App\Domain\Candidate\NormalizationContext;
use App\Domain\Candidate\NormalizationFinding;
use App\Domain\Candidate\SourceNormalizationResult;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use App\Domain\Ingestion\ParsedObservation;
use DateTimeImmutable;
use DateTimeZone;
use JsonException;

final class AdemeCandidateNormalizer implements SourceNormalizationAdapter
{
    public const NORMALIZER_VERSION = '1.0.0';

    private const VALID_FACTOR_STATUSES = [
        'Valide générique',
        'Valide spécifique',
    ];

    private const GAS_FIELDS = [
        'CO2f' => ['code' => 'CO2_fossil', 'basis' => 'source_reported_gas_component'],
        'CH4f' => ['code' => 'CH4_fossil', 'basis' => 'source_reported_gas_component'],
        'CH4b' => ['code' => 'CH4_biogenic', 'basis' => 'source_reported_gas_component'],
        'N2O' => ['code' => 'N2O', 'basis' => 'source_reported_gas_component'],
        'Autres GES' => ['code' => 'other_ghg', 'basis' => 'source_reported_gas_component'],
        'CO2b' => ['code' => 'CO2_biogenic', 'basis' => 'source_reported_gas_component'],
    ];

    public function sourceCode(): string
    {
        return 'ADEME';
    }

    public function normalizerVersion(): string
    {
        return self::NORMALIZER_VERSION;
    }

    public function normalize(iterable $observations, NormalizationContext $context): SourceNormalizationResult
    {
        $this->assertContext($context);
        $elements = [];
        $postsByElement = [];
        $inputCount = 0;

        foreach ($observations as $observation) {
            if (! $observation instanceof ParsedObservation) {
                throw new SourceContractViolation('ADEME normalizer received an invalid parsed observation.');
            }

            $inputCount++;

            if (! $this->isValidFactor($observation)) {
                continue;
            }

            if ($observation->recordType === 'Elément') {
                if (isset($elements[$observation->sourceRecordId])) {
                    throw new SourceContractViolation(
                        "ADEME normalizer received duplicate candidate element {$observation->sourceRecordId}.",
                    );
                }

                $elements[$observation->sourceRecordId] = $observation;
            } elseif ($observation->recordType === 'Poste') {
                $postsByElement[$observation->sourceRecordId][] = $observation;
            }
        }

        $findings = [];
        $attachedPosts = 0;
        $negativeTotals = 0;
        $missingTotals = 0;
        $missingUnits = 0;

        foreach ($elements as $elementId => $element) {
            $posts = $postsByElement[$elementId] ?? [];
            $attachedPosts += count($posts);
            $candidateFindings = $this->candidateFindings($element, $context);

            foreach ($candidateFindings as $finding) {
                $findings[] = $finding;

                if ($finding->code === 'negative_total_requires_methodology_review') {
                    $negativeTotals++;
                } elseif ($finding->code === 'primary_value_not_reported') {
                    $missingTotals++;
                } elseif ($finding->code === 'source_unit_not_reported') {
                    $missingUnits++;
                }
            }
        }

        $candidates = (function () use ($elements, $postsByElement, $context): \Generator {
            foreach ($elements as $elementId => $element) {
                yield $this->candidate($element, $postsByElement[$elementId] ?? [], $context);
            }
        })();

        return new SourceNormalizationResult(
            candidates: $candidates,
            findings: $findings,
            metrics: [
                'input_observations' => $inputCount,
                'candidate_entities' => count($elements),
                'attached_post_observations' => $attachedPosts,
                'negative_totals_requiring_review' => $negativeTotals,
                'missing_primary_values' => $missingTotals,
                'missing_source_units' => $missingUnits,
                'skipped_non_candidate_observations' => $inputCount - count($elements) - $attachedPosts,
            ],
        );
    }

    /**
     * @param  list<ParsedObservation>  $posts
     */
    private function candidate(
        ParsedObservation $element,
        array $posts,
        NormalizationContext $context,
    ): CandidateEntityDraft {
        $logicalKey = "ademe:{$context->datasetId}:{$element->sourceRecordId}";
        $candidateKey = "{$logicalKey}:release:{$context->releaseVersion}";
        $variantKey = $logicalKey.':variant:'.substr(hash('sha256', implode('|', [
            $this->field($element, 'Unité français'),
            $this->field($element, 'Localisation géographique'),
            $this->field($element, 'Sous-localisation géographique français'),
            $this->field($element, 'Nom frontière français'),
        ])), 0, 24);
        $methodologyKey = "{$candidateKey}:methodology";
        $primaryComponentKey = "{$candidateKey}:component:total";
        $provenanceKey = "{$candidateKey}:provenance:row:{$element->sourceRow}";
        $evidenceKey = "{$candidateKey}:evidence:row:{$element->sourceRow}";
        $unitProposalKey = "{$candidateKey}:mapping:unit";
        $taxonomyProposalKey = "{$candidateKey}:mapping:taxonomy";
        $intendedUseProposalKey = "{$candidateKey}:mapping:intended-use";
        $geographyProposalKey = "{$candidateKey}:geography:market";
        $total = $this->decimal($this->field($element, 'Total poste non décomposé'));
        $unit = $this->nullableField($element, 'Unité français');
        $primaryQuantity = $this->quantity($total, $unit, $unitProposalKey, [$provenanceKey]);
        $components = [[
            'component_key' => $primaryComponentKey,
            'value_kind' => 'co2e_total',
            'basis' => 'source_reported_total',
            'gas_code' => null,
            'quantity' => $primaryQuantity,
            'methodology_ref' => $methodologyKey,
            'provenance_refs' => [$provenanceKey],
        ]];
        $provenance = [$this->provenance($element, $provenanceKey, $context)];
        $evidence = [$this->evidence($element, $evidenceKey, $provenanceKey)];

        array_push(
            $components,
            ...$this->gasComponents(
                observation: $element,
                candidateKey: $candidateKey,
                componentScope: 'gas',
                basis: 'source_reported_gas_component',
                unit: $unit,
                unitProposalKey: $unitProposalKey,
                methodologyKey: $methodologyKey,
                provenanceKey: $provenanceKey,
            ),
        );

        foreach ($posts as $postIndex => $post) {
            $postProvenanceKey = "{$candidateKey}:provenance:row:{$post->sourceRow}";
            $postEvidenceKey = "{$candidateKey}:evidence:row:{$post->sourceRow}";
            $postUnit = $this->nullableField($post, 'Unité français') ?? $unit;
            $components[] = [
                'component_key' => "{$candidateKey}:component:lifecycle:".($postIndex + 1),
                'value_kind' => 'co2e_total',
                'basis' => 'lifecycle_stage',
                'gas_code' => null,
                'quantity' => $this->quantity(
                    $this->decimal($this->field($post, 'Total poste non décomposé')),
                    $postUnit,
                    $unitProposalKey,
                    [$postProvenanceKey],
                ),
                'methodology_ref' => $methodologyKey,
                'provenance_refs' => [$postProvenanceKey],
            ];
            array_push(
                $components,
                ...$this->gasComponents(
                    observation: $post,
                    candidateKey: $candidateKey,
                    componentScope: 'lifecycle:'.($postIndex + 1).':gas',
                    basis: 'lifecycle_stage_gas_component',
                    unit: $postUnit,
                    unitProposalKey: $unitProposalKey,
                    methodologyKey: $methodologyKey,
                    provenanceKey: $postProvenanceKey,
                ),
            );
            $provenance[] = $this->provenance($post, $postProvenanceKey, $context);
            $evidence[] = $this->evidence($post, $postEvidenceKey, $postProvenanceKey);
        }

        $taxonomyCode = $this->nullableField($element, 'Code de la catégorie') ?? 'not_reported';
        $geography = $this->geographyLabel($element);

        return new CandidateEntityDraft(
            schemaVersion: $context->candidateSchemaVersion,
            candidateKey: $candidateKey,
            logicalKey: $logicalKey,
            variantKey: $variantKey,
            valueKind: 'co2e_total',
            intendedUse: ['source_unspecified'],
            localizedTexts: $this->localizedTexts($element),
            sourceTaxonomy: [[
                'scheme' => 'ADEME_BASE_CARBONE',
                'code' => $taxonomyCode,
                'label' => $this->nullableField($element, 'Tags français'),
                'path' => [],
                'provenance_refs' => [$provenanceKey],
            ]],
            primaryComponentKey: $primaryComponentKey,
            primaryQuantity: $primaryQuantity,
            components: $components,
            temporal: $this->temporal($element, $context, $provenanceKey),
            methodology: $this->methodology($element, $posts, $methodologyKey, $provenanceKey),
            geographyProposals: [[
                'proposal_key' => $geographyProposalKey,
                'role' => 'market',
                'raw_code' => null,
                'raw_label' => $geography,
                'status' => 'unresolved',
                'target' => null,
                'confidence' => null,
                'evidence_refs' => [$evidenceKey],
                'provenance_refs' => [$provenanceKey],
            ]],
            canonicalMappingProposals: [
                $this->mapping($unitProposalKey, 'unit', $unit, $evidenceKey, $provenanceKey),
                $this->mapping($taxonomyProposalKey, 'taxonomy', $taxonomyCode, $evidenceKey, $provenanceKey),
                $this->mapping($intendedUseProposalKey, 'intended_use', null, $evidenceKey, $provenanceKey),
            ],
            reportingApplicabilityProposals: [],
            relationships: [],
            evidence: $evidence,
            provenance: $provenance,
            extensions: [],
        );
    }

    /** @return list<NormalizationFinding> */
    private function candidateFindings(
        ParsedObservation $element,
        NormalizationContext $context,
    ): array {
        $candidateKey = "ademe:{$context->datasetId}:{$element->sourceRecordId}:release:{$context->releaseVersion}";
        $total = $this->decimal($this->field($element, 'Total poste non décomposé'));
        $findings = [];

        if ($total !== null && str_starts_with($total, '-')) {
            $findings[] = new NormalizationFinding(
                code: 'negative_total_requires_methodology_review',
                severity: 'review',
                candidateKey: $candidateKey,
                message: 'Negative ADEME total was preserved without assigning avoided-emission semantics.',
                context: ['source_row' => $element->sourceRow, 'source_value' => $total],
            );
        }

        if ($total === null) {
            $findings[] = new NormalizationFinding(
                code: 'primary_value_not_reported',
                severity: 'blocking',
                candidateKey: $candidateKey,
                message: 'ADEME candidate has no reported primary quantity.',
                context: ['source_row' => $element->sourceRow],
            );
        }

        if ($this->nullableField($element, 'Unité français') === null) {
            $findings[] = new NormalizationFinding(
                code: 'source_unit_not_reported',
                severity: 'blocking',
                candidateKey: $candidateKey,
                message: 'ADEME candidate has no reported source unit.',
                context: ['source_row' => $element->sourceRow],
            );
        }

        return $findings;
    }

    private function assertContext(NormalizationContext $context): void
    {
        if ($context->sourceCode !== $this->sourceCode() || $context->datasetId !== 'base-carboner') {
            throw new SourceContractViolation('ADEME normalizer received a foreign source context.');
        }
    }

    private function isValidFactor(ParsedObservation $observation): bool
    {
        return $observation->elementType === "Facteur d'émission"
            && in_array($observation->status, self::VALID_FACTOR_STATUSES, true)
            && in_array($observation->recordType, ['Elément', 'Poste'], true);
    }

    /** @return non-empty-list<array<string, mixed>> */
    private function localizedTexts(ParsedObservation $element): array
    {
        $texts = [];

        foreach ([
            'fr' => ['Nom base français', 'Nom attribut français', 'Commentaire français'],
            'en' => ['Nom base anglais', 'Nom attribut anglais', 'Commentaire anglais'],
            'es' => ['Nom base espagnol', 'Nom attribut espagnol', 'Commentaire espagnol'],
        ] as $locale => [$baseField, $attributeField, $descriptionField]) {
            $base = $this->nullableField($element, $baseField);
            $attribute = $this->nullableField($element, $attributeField);

            if ($base === null && $attribute === null) {
                continue;
            }

            $texts[] = [
                'locale' => $locale,
                'label' => implode(' / ', array_values(array_filter([$base, $attribute]))),
                'description' => $this->nullableField($element, $descriptionField),
            ];
        }

        if ($texts === []) {
            $texts[] = [
                'locale' => 'fr',
                'label' => "ADEME Base Carbone {$element->sourceRecordId}",
                'description' => null,
            ];
        }

        return $texts;
    }

    /**
     * @param  list<string>  $provenanceRefs
     * @return array<string, mixed>
     */
    private function quantity(?string $value, ?string $unit, string $unitProposalKey, array $provenanceRefs): array
    {
        return [
            'value_state' => $value === null ? 'not_reported' : 'known',
            'value' => $value,
            'value_reason_code' => $value === null ? 'not_reported' : null,
            'source_precision' => null,
            'output_unit' => [
                'raw_code' => null,
                'raw_label' => $unit,
                'mapping_proposal_key' => $unitProposalKey,
            ],
            'activity_unit' => null,
            'basis_qualifiers' => [],
            'provenance_refs' => $provenanceRefs,
        ];
    }

    /** @return list<array<string, mixed>> */
    private function gasComponents(
        ParsedObservation $observation,
        string $candidateKey,
        string $componentScope,
        string $basis,
        ?string $unit,
        string $unitProposalKey,
        string $methodologyKey,
        string $provenanceKey,
    ): array {
        $components = [];

        foreach (self::GAS_FIELDS as $field => $definition) {
            $value = $this->decimal($this->field($observation, $field));

            if ($value === null) {
                continue;
            }

            $components[] = [
                'component_key' => "{$candidateKey}:component:{$componentScope}:".$this->code($definition['code']),
                'value_kind' => 'gas_emission_factor',
                'basis' => $basis,
                'gas_code' => $definition['code'],
                'quantity' => $this->quantity($value, $unit, $unitProposalKey, [$provenanceKey]),
                'methodology_ref' => $methodologyKey,
                'provenance_refs' => [$provenanceKey],
            ];
        }

        for ($index = 1; $index <= 5; $index++) {
            $gasCode = $this->nullableField($observation, "Code gaz supplémentaire {$index}");
            $value = $this->decimal($this->field($observation, "Valeur gaz supplémentaire {$index}"));

            if ($gasCode === null || $value === null) {
                continue;
            }

            $components[] = [
                'component_key' => "{$candidateKey}:component:{$componentScope}:additional:{$index}",
                'value_kind' => 'gas_emission_factor',
                'basis' => $basis,
                'gas_code' => $gasCode,
                'quantity' => $this->quantity($value, $unit, $unitProposalKey, [$provenanceKey]),
                'methodology_ref' => $methodologyKey,
                'provenance_refs' => [$provenanceKey],
            ];
        }

        return $components;
    }

    /** @return array<string, mixed> */
    private function temporal(
        ParsedObservation $element,
        NormalizationContext $context,
        string $provenanceKey,
    ): array {
        $period = $this->nullableField($element, 'Période de validité');
        $referencePeriod = [
            'kind' => 'unknown',
            'year' => null,
            'start' => null,
            'end' => null,
            'label' => null,
        ];

        if ($period !== null && preg_match('/^(?:Année\s+)?(19\d{2}|20\d{2})$/u', $period, $matches) === 1) {
            $referencePeriod['kind'] = 'year';
            $referencePeriod['year'] = (int) $matches[1];
        } elseif ($period !== null) {
            $referencePeriod['kind'] = 'label';
            $referencePeriod['label'] = $period;
        }

        return [
            'reference_period' => $referencePeriod,
            'validity' => ['valid_from' => null, 'valid_to' => null],
            'source_published_at' => $this->dateTime($context->sourcePublishedAt),
            'retrieved_at' => $this->dateTime($context->retrievedAt),
            'provenance_refs' => [$provenanceKey],
        ];
    }

    /**
     * @param  list<ParsedObservation>  $posts
     * @return array<string, mixed>
     */
    private function methodology(
        ParsedObservation $element,
        array $posts,
        string $methodologyKey,
        string $provenanceKey,
    ): array {
        $stages = [];

        foreach ($posts as $post) {
            $stage = $this->nullableField($post, 'Type poste');

            if ($stage !== null) {
                $stages[] = 'ademe.'.substr(hash('sha256', $stage), 0, 16);
            }
        }

        return [
            'methodology_key' => $methodologyKey,
            'methodology_code' => $this->nullableField($element, 'Programme'),
            'methodology_version' => null,
            'boundary_code' => $this->nullableField($element, 'Nom frontière français'),
            'lifecycle_stage_codes' => array_values(array_unique($stages)),
            'scenario_code' => null,
            'gwp' => null,
            'formula_or_recipe_ref' => null,
            'provenance_refs' => [$provenanceKey],
        ];
    }

    /** @return array<string, mixed> */
    private function mapping(
        string $proposalKey,
        string $domain,
        ?string $sourceValue,
        string $evidenceKey,
        string $provenanceKey,
    ): array {
        return [
            'proposal_key' => $proposalKey,
            'domain' => $domain,
            'source_value' => $sourceValue,
            'status' => 'unresolved',
            'target' => null,
            'confidence' => null,
            'ruleset_version' => 'ademe.source-proposals.v1.0.0',
            'evidence_refs' => [$evidenceKey],
            'provenance_refs' => [$provenanceKey],
        ];
    }

    /** @return array<string, mixed> */
    private function evidence(ParsedObservation $observation, string $key, string $provenanceKey): array
    {
        $summary = $observation->recordType === 'Poste'
            ? 'ADEME lifecycle decomposition row: '
                .($this->nullableField($observation, 'Type poste') ?? 'untyped').' / '
                .($this->nullableField($observation, 'Nom poste français') ?? 'unnamed')
            : 'ADEME emission factor element row.';

        return [
            'evidence_key' => $key,
            'kind' => 'source_row',
            'summary' => $summary,
            'source_reference' => "row:{$observation->sourceRow}",
            'provenance_refs' => [$provenanceKey],
        ];
    }

    /** @return array<string, mixed> */
    private function provenance(
        ParsedObservation $observation,
        string $key,
        NormalizationContext $context,
    ): array {
        return [
            'provenance_key' => $key,
            'field_pointers' => [''],
            'source_asset_key' => $context->rawAssetKey,
            'source_asset_sha256' => $context->rawAssetSha256,
            'locator' => [
                'kind' => 'csv_cell',
                'file_path' => $context->rawAssetKey,
                'sheet' => null,
                'table' => 'Base Carbone',
                'row' => $observation->sourceRow,
                'column' => null,
                'cell' => null,
                'json_pointer' => null,
                'byte_start' => null,
                'byte_end' => null,
            ],
            'raw_value' => $this->provenanceRawValue($observation),
            'transform_chain' => [[
                'operation' => 'ademe_candidate_normalization',
                'version' => self::NORMALIZER_VERSION,
            ]],
        ];
    }

    private function provenanceRawValue(ParsedObservation $observation): string
    {
        try {
            return json_encode([
                'record_type' => $observation->recordType,
                'name' => $this->nullableField($observation, 'Nom base français')
                    ?? $this->nullableField($observation, 'Nom poste français'),
                'total' => $this->nullableField($observation, 'Total poste non décomposé'),
                'unit' => $this->nullableField($observation, 'Unité français'),
                'geography' => $this->geographyLabel($observation),
            ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        } catch (JsonException $exception) {
            throw new SourceContractViolation('ADEME provenance could not be encoded.', previous: $exception);
        }
    }

    private function geographyLabel(ParsedObservation $observation): ?string
    {
        $location = $this->nullableField($observation, 'Localisation géographique');
        $subLocation = $this->nullableField($observation, 'Sous-localisation géographique français');

        return match (true) {
            $location !== null && $subLocation !== null => "{$location} / {$subLocation}",
            $location !== null => $location,
            default => $subLocation,
        };
    }

    private function nullableField(ParsedObservation $observation, string $name): ?string
    {
        $value = trim($this->field($observation, $name));

        return $value === '' ? null : $value;
    }

    private function field(ParsedObservation $observation, string $name): string
    {
        return $observation->fields[$name] ?? '';
    }

    private function decimal(string $value): ?string
    {
        $value = preg_replace('/[\s\x{00A0}\x{202F}]+/u', '', trim($value));

        if (! is_string($value) || $value === '') {
            return null;
        }

        $value = str_replace(',', '.', $value);

        if (preg_match('/^([+-]?)(\d*)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/D', $value, $matches) !== 1
            || ($matches[2] ?? '') === '' && ($matches[3] ?? '') === ''
        ) {
            throw new SourceContractViolation("ADEME normalizer received an invalid decimal: {$value}.");
        }

        $sign = ($matches[1] ?? '') === '-' ? '-' : '';
        $integer = $matches[2] ?? '';
        $fraction = $matches[3] ?? '';
        $exponent = (int) ($matches[4] ?? 0);
        $digits = $integer.$fraction;
        $decimalPosition = strlen($integer) + $exponent;

        if (strlen($digits) > 128 || $exponent < -128 || $exponent > 128) {
            throw new SourceContractViolation('ADEME normalized decimal exceeds the candidate contract limit.');
        }

        if ($decimalPosition <= 0) {
            $expanded = '0.'.str_repeat('0', -$decimalPosition).$digits;
        } elseif ($decimalPosition >= strlen($digits)) {
            $expanded = $digits.str_repeat('0', $decimalPosition - strlen($digits));
        } else {
            $expanded = substr($digits, 0, $decimalPosition).'.'.substr($digits, $decimalPosition);
        }

        [$whole, $decimal] = array_pad(explode('.', $expanded, 2), 2, '');
        $whole = ltrim($whole, '0');
        $decimal = rtrim($decimal, '0');
        $canonical = ($whole === '' ? '0' : $whole).($decimal === '' ? '' : ".{$decimal}");

        if ($canonical === '0') {
            return '0';
        }

        $canonical = $sign.$canonical;

        if (strlen($canonical) > 128) {
            throw new SourceContractViolation('ADEME normalized decimal exceeds the candidate contract limit.');
        }

        return $canonical;
    }

    private function code(string $value): string
    {
        return strtolower(preg_replace('/[^A-Za-z0-9_]+/', '_', $value) ?? 'unknown');
    }

    private function dateTime(?DateTimeImmutable $dateTime): ?string
    {
        return $dateTime?->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d\TH:i:s\Z');
    }
}
