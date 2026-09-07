<?php

use App\Actions\AtlasCatalogSnapshot\AtlasDeliveryContract;
use App\Actions\AtlasCatalogSnapshot\LookupReviewCatalog;
use App\Actions\AtlasCatalogSnapshot\ReadDeliveryCatalog;
use App\Actions\AtlasCatalogSnapshot\ReviewCatalogContract;
use App\Actions\FactorContext\FactorContextContract;
use App\Actions\UnitCatalogRelease\CanonicalUnitCatalogJson;
use Illuminate\Foundation\Application;
use Illuminate\Support\Facades\Facade;
use Illuminate\Support\Facades\Storage;

// Run through Admin's existing PHP runner. Only /tmp synthetic artifacts are written.
require '/var/www/html/vendor/autoload.php';
$app = new Application('/var/www/html');
Facade::setFacadeApplication($app);
$json = new CanonicalUnitCatalogJson;
$contract = new AtlasDeliveryContract($json);
$review = new ReviewCatalogContract($json);
$factor = new FactorContextContract;
$read = new ReadDeliveryCatalog($json, $factor, $review, $contract);
$temp = sys_get_temp_dir().'/atlas-admin-review-'.bin2hex(random_bytes(8));
mkdir($temp);
$files = [];
$fake = new class($temp)
{
    public array $streams = [];

    public function __construct(private string $root) {}

    public function disk($name)
    {
        return $this;
    }

    public function path($name)
    {
        return $this->root.'/'.hash('sha256', $name);
    }

    public function readStream($name)
    {
        $stream = fopen('php://temp', 'w+b');
        fwrite($stream, $this->streams[$name]);
        rewind($stream);

        return $stream;
    }
};
Storage::swap($fake);
try {
    $currency = ['schema_version' => 'netzero-currency-snapshot/v1', 'owner' => 'NetZeroAdmin',
        'policy' => ['fx_conversion' => false, 'scientific_dimension' => false, 'symbols_are_aliases' => false],
        'currencies' => [['id' => '01a00000-0000-7000-8000-000000000011', 'code' => 'EUR', 'name' => 'TEST ONLY Euro',
            'symbol' => '€', 'active' => true, 'deleted' => false, 'usable' => true, 'sha256' => str_repeat('0', 64)]]];
    $bytes = $json->encode($currency);
    $hash = hash('sha256', $bytes);
    $path = 'atlas-catalog-snapshots/currency/sha256/'.$hash.'.json';
    $descriptor = ['schema_version' => 'netzero-currency-snapshot-descriptor/v1', 'owner' => 'NetZeroAdmin', 'catalog' => 'currency',
        'version' => 'sha256:'.$hash, 'content_schema_version' => 'netzero-currency-snapshot/v1', 'canonicalization' => 'netzero-sorted-json-v1',
        'sha256' => $hash, 'size_bytes' => strlen($bytes), 'artifact_path' => $path];
    foreach ([$path => $bytes, $path.'.manifest.json' => $json->encode($descriptor)] as $name => $content) {
        $file = $fake->path($name);
        file_put_contents($file, $content);
        $files[] = $file;
    }
    $accepted = $read->handle('currency', $hash);
    echo json_encode(['case' => 'currency entry hash is all zeros; outer bytes/hash valid', 'Admin_ReadDeliveryCatalog_accepted' => isset($accepted['descriptor']),
        'entry_hash_valid' => false, 'expected' => 'reject inconsistent entry hash']).PHP_EOL;

    $u = fn ($i) => '01a00000-0000-7000-8000-'.str_pad((string) $i, 12, '0', STR_PAD_LEFT);
    $kinds = ['protocol', 'scope', 'segment', 'category', 'consumption_type', 'material'];
    $ids = [];
    foreach ($kinds as $i => $kind) {
        $ids[$kind] = $u(20 + $i);
    }
    $nodes = [];
    foreach ($kinds as $kind) {
        $parents = match ($kind) {
            'segment' => ['scope:'.$ids['scope'], 'protocol:'.$ids['protocol']],
            'category' => ['segment:'.$ids['segment']],'material' => ['consumption_type:'.$ids['consumption_type']],default => []
        };
        $node = ['id' => $ids[$kind], 'canonical_id' => $kind.':'.$ids[$kind], 'kind' => $kind, 'parents' => $parents,
            'names' => [], 'active' => true, 'deleted' => false, 'main' => null, 'sort_order' => 1];
        $nodes[] = [...$node, 'sha256' => $json->hash($node)];
    }
    $link = ['id' => $u(30), 'category_id' => $ids['category'], 'consumption_type_id' => $ids['consumption_type'], 'deleted' => false, 'sort_order' => 1];
    $taxonomy = ['schema_version' => 'netzero-taxonomy-snapshot/v1', 'owner' => 'NetZeroAdmin', 'policy' => $review::POLICY,
        'nodes' => $nodes, 'category_consumption_links' => [[...$link, 'sha256' => $json->hash($link)]]];
    $review->assertValid('taxonomy', $taxonomy);
    $bytes = $json->encode($taxonomy);
    $hash = hash('sha256', $bytes);
    $path = 'atlas-catalog-snapshots/taxonomy/sha256/'.$hash.'.json';
    $descriptor = ['schema_version' => 'netzero-review-catalog-descriptor/v1', 'owner' => 'NetZeroAdmin', 'catalog' => 'taxonomy',
        'version' => 'sha256:'.$hash, 'content_schema_version' => 'netzero-taxonomy-snapshot/v1', 'canonicalization' => 'netzero-sorted-json-v1',
        'sha256' => $hash, 'size_bytes' => strlen($bytes), 'artifact_path' => $path];
    $fake->streams = [$path => $bytes, $path.'.manifest.json' => $json->encode($descriptor)];
    $result = (new LookupReviewCatalog($review, $json))->taxonomyPath('sha256:'.$hash, $hash, $ids);
    echo json_encode(['case' => 'valid taxonomy with segment parent order scope, protocol', 'Admin_contract_accepted' => true,
        'Admin_lookup_status' => $result['status'], 'expected' => 'registered for the same typed graph']).PHP_EOL;
} finally {
    foreach ($files as $file) {
        unlink($file);
    } rmdir($temp);
}
