<?php

namespace Tests\Feature;

use App\Domain\Catalog\CatalogType;
use App\Domain\Catalog\ReviewCatalogLookup;
use App\Infrastructure\Catalog\VerifyAtlasDelivery;
use Tests\Support\DeliveryFixture;
use Tests\TestCase;

final class ReviewDeliveryLookupTest extends TestCase
{
    public function test_parent_order_does_not_change_graph_and_inactive_ancestor_blocks_the_path(): void
    {
        $fixture = new DeliveryFixture;
        $pin = array_values(array_filter($fixture->catalogs, fn ($p) => $p['catalog'] === 'taxonomy'))[0];
        $payload = json_decode($fixture->files[$pin['artifact_name']], true);
        $context = [];
        foreach ($payload['nodes'] as &$node) {
            $context[$node['kind']] = $node['id'];
            if ($node['kind'] === 'segment') {
                $node['parents'] = array_reverse($node['parents']);
                unset($node['sha256']);
                $node['sha256'] = hash('sha256', DeliveryFixture::json($node));
            }
        }
        unset($node);
        unset($fixture->catalogs['taxonomy:'.$pin['sha256']], $fixture->files[$pin['artifact_name']], $fixture->files[$pin['descriptor_name']]);
        $fixture->catalog('taxonomy', $payload);
        $package = $fixture->package();
        $verified = app(VerifyAtlasDelivery::class)->verify($package['hash'], DeliveryFixture::read($package['objects']));
        $hash = hash('sha256', DeliveryFixture::json($payload));
        $snapshot = $verified->catalog(CatalogType::Taxonomy, 'sha256:'.$hash, $hash);
        $lookup = new ReviewCatalogLookup;

        $result = $lookup->taxonomyPath($snapshot, $context);

        $this->assertSame('registered', $result['status']);
        $this->assertCount(6, $result['targets']);
        $this->assertFalse($result['usage_allowed']);
        $this->assertFalse($result['publish_allowed']);
        $this->assertSame('unresolved', $lookup->lookup($snapshot, 'TEST label')['status']);
        foreach ($payload['nodes'] as &$node) {
            if ($node['kind'] === 'protocol') {
                $node['active'] = false;
                unset($node['sha256']);
                $node['sha256'] = hash('sha256', DeliveryFixture::json($node));
            }
        }
        unset($node);
        $old = $fixture->catalogs['taxonomy:'.$hash];
        unset($fixture->catalogs['taxonomy:'.$hash], $fixture->files[$old['artifact_name']], $fixture->files[$old['descriptor_name']]);
        $fixture->catalog('taxonomy', $payload);
        $package = $fixture->package();
        $verified = app(VerifyAtlasDelivery::class)->verify($package['hash'], DeliveryFixture::read($package['objects']));
        $hash = hash('sha256', DeliveryFixture::json($payload));
        $snapshot = $verified->catalog(CatalogType::Taxonomy, 'sha256:'.$hash, $hash);
        $this->assertSame('inactive', $lookup->taxonomyPath($snapshot, $context)['status']);
        $this->assertSame('inactive', $lookup->lookup($snapshot, 'category:'.$context['category'])['status']);
    }
}
