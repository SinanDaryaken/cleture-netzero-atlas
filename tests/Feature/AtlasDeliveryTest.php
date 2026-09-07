<?php

namespace Tests\Feature;

use App\Application\Catalog\TransferAtlasDelivery;
use App\Domain\Catalog\CatalogType;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use App\Domain\Catalog\ReviewCatalogLookup;
use App\Domain\Catalog\SortedCatalogJson;
use App\Infrastructure\Catalog\DeliveryCatalogSnapshotLoader;
use App\Infrastructure\Catalog\LocalDeliveryDirectory;
use App\Infrastructure\Catalog\VerifyAtlasDelivery;
use App\Infrastructure\Catalog\VerifyDeliveredResolution;
use App\Infrastructure\Contracts\PinnedDeliveryContracts;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\Support\DeliveryFixture;
use Tests\Support\InMemoryDeliveryStore;
use Tests\TestCase;

final class AtlasDeliveryTest extends TestCase
{
    public function test_five_catalogs_round_trip_with_python_hash_oracle_and_idempotent_manifest_last_transfer(): void
    {
        $package = (new DeliveryFixture)->package();
        $store = new InMemoryDeliveryStore;
        $transfer = new TransferAtlasDelivery(app(VerifyAtlasDelivery::class), $store);
        $first = $transfer->transfer($package['hash'], DeliveryFixture::read($package['objects']));
        $before = $store->objects;

        $second = $transfer->transfer($package['hash'], DeliveryFixture::read($package['objects']));

        $this->assertSame($before, $store->objects);
        $this->assertSame('manifest.json', end($store->writes));
        $this->assertSame(DeliveryFixture::json($first->receipt()), DeliveryFixture::json($second->receipt()));
        $oracle = json_decode(file_get_contents(base_path('tests/fixtures/atlas-delivery/oracle.json')), true);
        $unit = $second->catalog(CatalogType::Unit, 'TEST-base-v1', $oracle['unit_sha256']);
        $this->assertSame($oracle['unit_definition_sha256'], $unit->payload['definitions'][0]['sha256']);
        $this->assertCount(5, $second->catalogs);
        $pins = [];
        foreach ($second->manifest->catalogs as $pin) {
            $pins[$pin->catalog] = ['version' => $pin->version, 'sha256' => $pin->sha256];
        }
        $loader = new DeliveryCatalogSnapshotLoader($transfer, $package['hash'], $pins);
        foreach (CatalogType::cases() as $type) {
            $this->assertSame($pins[$type->value]['sha256'], $loader->load($type)->descriptor->sha256);
        }
        $lookup = (new ReviewCatalogLookup)->lookup($loader->load(CatalogType::IntendedUse), 'corporate_carbon_footprint');
        $this->assertSame('registered', $lookup['status']);
        $this->assertFalse($lookup['usage_allowed']);
        $this->assertFalse($lookup['publish_allowed']);
        $this->assertFalse($second->receipt()['current_approval_verified']);
    }

    public static function byteDamage(): array
    {
        return [['missing_manifest'], ['manifest_hash'], ['missing_object'], ['corrupt_object']];
    }

    #[DataProvider('byteDamage')]
    public function test_missing_or_corrupt_bytes_never_fall_back(string $damage): void
    {
        $package = (new DeliveryFixture)->package();
        $object = $package['manifest']['artifacts'][0]['object_path'];
        match ($damage) {
            'missing_manifest' => $package['objects'] = array_diff_key($package['objects'], ['manifest.json' => true]),
            'manifest_hash' => $package['hash'] = str_repeat('0', 64),
            'missing_object' => $package['objects'] = array_diff_key($package['objects'], [$object => true]),
            'corrupt_object' => $package['objects'][$object] = 'corrupt',
        };
        $this->expectException(CatalogContractViolation::class);

        app(VerifyAtlasDelivery::class)->verify($package['hash'], DeliveryFixture::read($package['objects']));
    }

    public static function semanticDamage(): array
    {
        return [['descriptor_version'], ['descriptor_content_schema'], ['descriptor_catalog'], ['payload_schema'],
            ['schema_hash'], ['missing_schema'], ['unit_entry_hash'], ['unit_kind'], ['currency_usability'], ['taxonomy_parent'], ['usage_permission']];
    }

    #[DataProvider('semanticDamage')]
    public function test_rehashed_package_cannot_hide_semantic_or_trust_mismatches(string $damage): void
    {
        $fixture = new DeliveryFixture;
        $pin = array_values($fixture->catalogs)[0];
        if (str_starts_with($damage, 'descriptor_')) {
            $descriptor = json_decode($fixture->files[$pin['descriptor_name']], true);
            $field = match ($damage) {
                'descriptor_version' => 'version', 'descriptor_catalog' => 'catalog', default => 'content_schema_version'
            };
            $descriptor[$field] = 'wrong';
            $fixture->files[$pin['descriptor_name']] = DeliveryFixture::json($descriptor);
        } elseif ($damage === 'schema_hash') {
            $fixture->files['contracts/atlas-delivery-v1.schema.json'] = '{}';
        } elseif ($damage === 'missing_schema') {
            unset($fixture->files['contracts/atlas-delivery-v1.schema.json']);
        } else {
            $type = match ($damage) {
                'unit_entry_hash', 'unit_kind' => 'unit', 'taxonomy_parent' => 'taxonomy', 'usage_permission' => 'intended_use', default => 'currency'
            };
            $pin = array_values(array_filter($fixture->catalogs, fn ($pin) => $pin['catalog'] === $type))[0];
            $payload = json_decode($fixture->files[$pin['artifact_name']], true);
            match ($damage) {
                'payload_schema' => $payload['schema_version'] = 'latest',
                'unit_entry_hash' => $payload['definitions'][0]['sha256'] = str_repeat('0', 64),
                'unit_kind' => $payload['definitions'][0]['quantity_kind_id'] = '01a00000-0000-7000-8000-000000000099',
                'currency_usability' => $payload['currencies'][0]['usable'] = false,
                'taxonomy_parent' => $payload['nodes'][0]['parents'] = ['scope:01a00000-0000-7000-8000-000000000021'],
                'usage_permission' => $payload['policy']['applicability_inferred'] = true,
            };
            // Rehash individual entries too: lifecycle and graph checks must add protection beyond hashes.
            if (in_array($damage, ['currency_usability', 'taxonomy_parent'], true)) {
                $key = $damage === 'currency_usability' ? 'currencies' : 'nodes';
                $entry = $payload[$key][0];
                unset($entry['sha256']);
                $payload[$key][0]['sha256'] = hash('sha256', DeliveryFixture::json($entry));
            }
            unset($fixture->catalogs[$type.':'.$pin['sha256']], $fixture->files[$pin['artifact_name']], $fixture->files[$pin['descriptor_name']]);
            $fixture->catalog($type, $payload);
        }
        $package = $fixture->package();
        $this->expectException(CatalogContractViolation::class);

        app(VerifyAtlasDelivery::class)->verify($package['hash'], DeliveryFixture::read($package['objects']));
    }

    public static function manifestDamage(): array
    {
        return [['unsafe_name'], ['unsafe_object'], ['duplicate'], ['catalog_version'], ['catalog_hash']];
    }

    #[DataProvider('manifestDamage')]
    public function test_rejects_manifest_relationships_even_with_matching_manifest_hash(string $damage): void
    {
        $package = (new DeliveryFixture)->package(function (array $manifest) use ($damage): array {
            match ($damage) {
                'unsafe_name' => $manifest['artifacts'][0]['name'] = '../outside',
                'unsafe_object' => $manifest['artifacts'][0]['object_path'] = 'objects/../outside',
                'duplicate' => $manifest['artifacts'][] = $manifest['artifacts'][0],
                'catalog_version' => $manifest['catalogs'][0]['version'] = 'wrong-version',
                'catalog_hash' => $manifest['catalogs'][0]['sha256'] = str_repeat('0', 64),
            };

            return $manifest;
        });
        $this->expectException(CatalogContractViolation::class);

        app(VerifyAtlasDelivery::class)->verify($package['hash'], DeliveryFixture::read($package['objects']));
    }

    public function test_interruption_has_no_commit_marker_retry_completes_and_conflicts_preserve_bytes(): void
    {
        $package = (new DeliveryFixture)->package();
        $store = new InMemoryDeliveryStore;
        $store->failAfter = 2;
        $transfer = new TransferAtlasDelivery(app(VerifyAtlasDelivery::class), $store);
        $this->invalid(fn () => $transfer->transfer($package['hash'], DeliveryFixture::read($package['objects'])));
        $this->assertArrayNotHasKey($package['hash'].'/manifest.json', $store->objects);
        $this->invalid(fn () => $transfer->read($package['hash']));
        $store->failAfter = null;
        $transfer->transfer($package['hash'], DeliveryFixture::read($package['objects']));
        $key = $package['hash'].'/'.$package['manifest']['artifacts'][0]['object_path'];
        $store->objects[$key] = 'conflict';

        $this->invalid(fn () => $transfer->transfer($package['hash'], DeliveryFixture::read($package['objects'])));

        $this->assertSame('conflict', $store->objects[$key]);
    }

    public static function resolutionTypes(): array
    {
        return array_map(fn ($type) => [$type], ['alias', 'new_unit', 'new_quantity_kind', 'exact_conversion', 'context_relation', 'monetary_measure']);
    }

    #[DataProvider('resolutionTypes')]
    public function test_synthetic_resolution_evidence_is_preserved_but_never_becomes_current_authority(string $type): void
    {
        $fixture = new DeliveryFixture($type);
        $package = $fixture->package();
        $delivery = app(VerifyAtlasDelivery::class)->verify($package['hash'], DeliveryFixture::read($package['objects']));
        $this->assertSame($fixture->files['resolution/payload.json'], $delivery->artifacts['resolution/payload.json']);
        $this->assertSame($type, $delivery->manifest->resolution->proposal_type);
        $this->assertSame('forensic_only', $delivery->receipt()['resolution_status']);
        $this->assertFalse($delivery->receipt()['current_approval_verified']);
        $this->expectException(CatalogContractViolation::class);
        $this->expectExceptionMessage('Current Admin approval channel is not contracted');

        app(VerifyDeliveredResolution::class)->requireCurrentApproval($delivery, $delivery->manifest->resolution);
    }

    public static function resolutionDamage(): array
    {
        return [['source'], ['raw'], ['revision'], ['decision_pin'], ['ruleset'], ['supersession'], ['rejected'], ['new_unit_without_target'], ['wrong_published_target'], ['base_catalog']];
    }

    #[DataProvider('resolutionDamage')]
    public function test_source_raw_revision_decision_and_publication_mismatches_fail_closed(string $damage): void
    {
        $fixture = new DeliveryFixture(in_array($damage, ['new_unit_without_target', 'wrong_published_target'], true) ? 'new_unit' : 'alias');
        match ($damage) {
            'source' => $fixture->resolution['source']['release'] = 'new-source-revision',
            'raw' => $fixture->files['source/raw'] = 'wrong raw',
            'revision' => $fixture->resolution['revision'] = 2,
            'decision_pin' => $fixture->resolution['decision_sha256'] = str_repeat('0', 64),
            'ruleset' => $fixture->resolution['ruleset_sha256'] = str_repeat('b', 64),
            'supersession' => $fixture->resolution['supersedes_decision_id'] = '01a00000-0000-7000-8000-000000000099',
            'new_unit_without_target' => $fixture->resolution['published_target'] = null,
            'wrong_published_target' => $fixture->resolution['published_target']['catalog_version'] = 'latest',
            default => null,
        };
        if ($damage === 'rejected') {
            $decision = json_decode($fixture->files['resolution/decision.json'], true);
            $decision['decision'] = 'reject';
            $fixture->files['resolution/decision.json'] = DeliveryFixture::json($decision);
            $fixture->resolution['decision_sha256'] = hash('sha256', $fixture->files['resolution/decision.json']);
        }
        if ($damage === 'base_catalog') {
            $resolution = json_decode($fixture->files['resolution/payload.json'], true);
            unset($fixture->catalogs['unit:'.$resolution['form']['unit_catalog_sha256']]);
        }
        $package = $fixture->package();
        $this->expectException(CatalogContractViolation::class);

        app(VerifyAtlasDelivery::class)->verify($package['hash'], DeliveryFixture::read($package['objects']));
    }

    public function test_expected_latest_decision_cannot_be_satisfied_by_old_delivered_approval(): void
    {
        $package = (new DeliveryFixture('alias'))->package();
        $delivery = app(VerifyAtlasDelivery::class)->verify($package['hash'], DeliveryFixture::read($package['objects']));
        $expected = clone $delivery->manifest->resolution;
        $expected->decision_sha256 = str_repeat('b', 64);
        $this->expectException(CatalogContractViolation::class);
        $this->expectExceptionMessage('Expected current source and decision pins');

        app(VerifyDeliveredResolution::class)->requireCurrentApproval($delivery, $expected);
    }

    public function test_sorted_json_preserves_empty_objects_null_uuid_and_decimal_strings(): void
    {
        $bytes = '{"decimal":"2.00000000000000000001","empty":{},"list":[],"null":null,"uuid":"01a00000-0000-7000-8000-000000000001"}';
        $json = new SortedCatalogJson;
        $value = $json->decode($bytes);
        $this->assertInstanceOf(\stdClass::class, $value->empty);
        $this->assertNull($value->null);
        $this->assertSame($bytes, $json->encode($value));
        $this->invalid(fn () => $json->decode('{"a":1,"a":1}'));
        $this->invalid(fn () => $json->decode('{"a":0.1}'));
        $this->invalid(fn () => $json->decode($bytes."\n"));
    }

    public function test_local_reader_rejects_traversal_and_parent_symlinks(): void
    {
        $root = sys_get_temp_dir().'/atlas-delivery-path-'.bin2hex(random_bytes(8));
        mkdir($root);
        mkdir($root.'/target');
        symlink($root.'/target', $root.'/objects');
        try {
            $reader = new LocalDeliveryDirectory($root);
            $this->invalid(fn () => $reader->read('../outside', 10));
            $this->invalid(fn () => $reader->read('objects/sha256/'.str_repeat('a', 64), 10));
        } finally {
            unlink($root.'/objects');
            rmdir($root.'/target');
            rmdir($root);
        }
    }

    public function test_independent_root_pin_rejects_changed_local_trust_manifest(): void
    {
        $root = sys_get_temp_dir().'/atlas-delivery-pin-'.bin2hex(random_bytes(8));
        mkdir($root);
        $file = 'atlas-delivery-contract-v1.manifest.json';
        file_put_contents($root.'/'.$file, '{}');
        try {
            $this->invalid(fn () => (new PinnedDeliveryContracts($root))->files([$file]));
        } finally {
            unlink($root.'/'.$file);
            rmdir($root);
        }
    }

    private function invalid(callable $operation): void
    {
        try {
            $operation();
            $this->fail('Invalid delivery was accepted.');
        } catch (CatalogContractViolation) {
            $this->addToAssertionCount(1);
        }
    }
}
