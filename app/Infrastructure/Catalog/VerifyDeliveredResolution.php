<?php

namespace App\Infrastructure\Catalog;

use App\Application\Contracts\CurrentApprovalClient;
use App\Application\Contracts\DeliveredResolutionApproval;
use App\Domain\Catalog\CatalogType;
use App\Domain\Catalog\CurrentApprovalObservation;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use App\Domain\Catalog\SortedCatalogJson;
use App\Domain\Catalog\VerifiedAtlasDelivery;
use App\Infrastructure\Contracts\PinnedDeliveryContracts;
use stdClass;

/** Historical evidence and a separate, non-authorizing current-state observation. */
final readonly class VerifyDeliveredResolution implements DeliveredResolutionApproval
{
    public function __construct(private SortedCatalogJson $json, private PinnedDeliveryContracts $contracts, private CurrentApprovalClient $currentApproval) {}

    public function verify(VerifiedAtlasDelivery $delivery): void
    {
        $pin = $delivery->manifest->resolution;
        if ($pin === null) {
            return;
        }
        $documents = [];
        foreach (['source/proposal.json' => 'proposal_sha256', 'source/receipt.json' => 'receipt_sha256',
            'resolution/payload.json' => 'resolution_sha256', 'resolution/decision.json' => 'decision_sha256'] as $name => $field) {
            $bytes = $delivery->artifacts[$name] ?? throw new CatalogContractViolation('Missing resolution evidence.');
            if (hash('sha256', $bytes) !== $pin->{$field}) {
                throw new CatalogContractViolation('Resolution evidence pin mismatch.');
            }
            $documents[$name] = $this->json->decode($bytes);
        }
        $proposal = $documents['source/proposal.json'];
        $receipt = $documents['source/receipt.json'];
        $resolution = $documents['resolution/payload.json'];
        $decision = $documents['resolution/decision.json'];
        $this->contracts->validate('source-proposal-v1.schema.json', $proposal);
        $raw = $delivery->artifacts['source/raw'] ?? throw new CatalogContractViolation('Missing raw source evidence.');
        $identity = hash('sha256', $this->json->encode(['source_code' => $pin->source->code, 'dataset' => $pin->source->dataset,
            'release' => $pin->source->release, 'raw_sha256' => $pin->source->raw->sha256, 'proposal_key' => $pin->proposal_key]));
        if ($this->json->encode($proposal->source) !== $this->json->encode($pin->source)
            || hash('sha256', $raw) !== $pin->source->raw->sha256 || strlen($raw) !== $pin->source->raw->size_bytes
            || $proposal->proposal_key !== $pin->proposal_key || $proposal->revision !== $pin->revision
            || $proposal->proposal->type !== $pin->proposal_type
            || $identity !== $pin->identity_sha256
            || ($receipt->schema_version ?? null) !== 'netzero-source-proposal-central-receipt/v1'
            || ($receipt->publish_allowed ?? null) !== false || ($receipt->canonical_write_allowed ?? null) !== false
            || ($receipt->proposal_sha256 ?? null) !== $pin->proposal_sha256
            || ($receipt->revision ?? null) !== $pin->revision || ($receipt->identity_sha256 ?? null) !== $pin->identity_sha256
            || ($resolution->schema_version ?? null) !== 'admin-source-resolution/1'
            || ($resolution->source_proposal_revision_id ?? null) !== $pin->revision_id
            || ($resolution->proposal_sha256 ?? null) !== $pin->proposal_sha256 || ($resolution->receipt_sha256 ?? null) !== $pin->receipt_sha256
            || ($resolution->version ?? null) !== $pin->resolution_version
            || ! property_exists($resolution, 'previous_resolution_id') || $resolution->previous_resolution_id !== $pin->previous_resolution_id
            || ($resolution->validation->ruleset_sha256 ?? null) !== $pin->ruleset_sha256
            || ($resolution->validation->errors ?? null) !== []
            || ($decision->source_proposal_resolution_id ?? null) !== $pin->resolution_id
            || ($decision->decision ?? null) !== 'approve' || ($decision->evidence_checked ?? null) !== true
            || ($decision->resolution_sha256 ?? null) !== $pin->resolution_sha256 || ($decision->ruleset_sha256 ?? null) !== $pin->ruleset_sha256
            || ! property_exists($decision, 'supersedes_decision_id') || $decision->supersedes_decision_id !== $pin->supersedes_decision_id
            || ($decision->publish_allowed ?? null) !== false || ($decision->canonical_write_allowed ?? null) !== false) {
            throw new CatalogContractViolation('Source/revision/resolution/decision/ruleset relationship mismatch.');
        }
        $baseHash = $resolution->form->unit_catalog_sha256 ?? null;
        if (! is_string($baseHash) || ! isset($delivery->catalogs['unit:'.$baseHash])) {
            throw new CatalogContractViolation('The original approved base catalog must be delivered exactly.');
        }
        // The validated proposal holds Admin's completed result; original proposal bytes stay untouched.
        if (! ($resolution->validation->proposal ?? null) instanceof stdClass) {
            throw new CatalogContractViolation('Missing validated resolution proposal.');
        }
        $completed = clone $proposal;
        $completed->proposal = $resolution->validation->proposal;
        $this->contracts->validate('source-proposal-v1.schema.json', $completed);
        $this->references($resolution->validation->proposal ?? null, $delivery);
        $scientific = in_array($pin->proposal_type, ['new_unit', 'new_quantity_kind'], true);
        if ($scientific !== ($pin->published_target !== null)) {
            throw new CatalogContractViolation('New scientific resolution requires an exact published target.');
        }
        if ($scientific) {
            $target = $pin->published_target;
            $snapshot = $delivery->catalog(CatalogType::Unit, $target->catalog_version, $target->catalog_sha256);
            $this->references($target, $delivery);
            $provenance = $this->json->decode($delivery->artifacts['resolution/scientific-provenance.json']
                ?? throw new CatalogContractViolation('Missing scientific provenance.'));
            $reference = $delivery->artifacts['resolution/scientific-reference.json']
                ?? throw new CatalogContractViolation('Missing published scientific reference.');
            $this->json->decode($reference);
            $matches = array_filter($snapshot->payload['definitions'], fn (array $entry): bool => $entry['id'] === $target->definition_id && $entry['scientific']['unit_definition']['source_id'] === 'resolution:'.$pin->resolution_id);
            if (count($matches) !== 1 || ($provenance->resolution_sha256 ?? null) !== $pin->resolution_sha256
                || ($provenance->decision_sha256 ?? null) !== $pin->decision_sha256
                || ($provenance->base_catalog_sha256 ?? null) !== $baseHash
                || ($provenance->unit_catalog_release_id ?? null) !== $snapshot->payload['release']['id']
                || ($provenance->reference_sha256 ?? null) !== hash('sha256', $reference)
                || $snapshot->payload['reference']['sha256'] !== hash('sha256', $reference)) {
                throw new CatalogContractViolation('Published scientific target is not linked to the exact approved evidence.');
            }
        }
    }

    /** The caller must supply the exact expected envelope, never latest/label defaults. */
    public function requireCurrentApproval(VerifiedAtlasDelivery $delivery, stdClass $expected): never
    {
        $this->inspectCurrentApproval($delivery, $expected);

        throw new CatalogContractViolation('Current approval is checked-at-only; authority body schemas and atomic finalization are not contracted. Usage remains blocked.');
    }

    public function inspectCurrentApproval(VerifiedAtlasDelivery $delivery, stdClass $expected): CurrentApprovalObservation
    {
        $this->verifyExpected($delivery, $expected);

        $resolution = $this->json->decode($delivery->artifacts['resolution/payload.json']);
        $hash = $resolution->form->unit_catalog_sha256;
        $base = $delivery->catalogs['unit:'.$hash]->descriptor;

        return $this->currentApproval->check($delivery->sha256, $expected, (object) ['version' => $base->version, 'sha256' => $hash]);
    }

    /** Local evidence preflight only; no network observation or usage authority. */
    public function verifyExpected(VerifiedAtlasDelivery $delivery, stdClass $expected): void
    {
        $this->verify($delivery);
        if ($delivery->manifest->resolution === null || $this->json->encode($delivery->manifest->resolution) !== $this->json->encode($expected)) {
            throw new CatalogContractViolation('Expected current source and decision pins do not match the delivery.');
        }
    }

    private function references(mixed $value, VerifiedAtlasDelivery $delivery): void
    {
        if (is_object($value) && isset($value->definition_id)) {
            $snapshot = $delivery->catalog(CatalogType::Unit, $value->catalog_version, $value->catalog_sha256);
            $matches = array_filter($snapshot->payload['definitions'], fn (array $entry): bool => $entry['id'] === $value->definition_id && $entry['sha256'] === $value->definition_sha256
                && $entry['quantity_kind_id'] === $value->quantity_kind_id && $entry['unit_code'] === $value->unit_code);
            if (count($matches) !== 1) {
                throw new CatalogContractViolation('Resolution references an unknown exact published definition.');
            }
        }
        if (is_object($value) && isset($value->currency_id)) {
            $snapshot = $delivery->catalog(CatalogType::Currency, $value->catalog_version, $value->catalog_sha256);
            $matches = array_filter($snapshot->payload['currencies'], fn (array $entry): bool => $entry['id'] === $value->currency_id
                && $entry['sha256'] === $value->entry_sha256 && $entry['code'] === $value->code && $entry['usable']);
            if (count($matches) !== 1) {
                throw new CatalogContractViolation('Resolution references an unavailable exact currency.');
            }
        }
        if (is_object($value) || is_array($value)) {
            foreach ($value as $child) {
                $this->references($child, $delivery);
            }
        }
    }
}
