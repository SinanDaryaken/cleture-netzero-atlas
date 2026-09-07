<?php

namespace App\Console\Commands;

use App\Application\Catalog\TransferAtlasDelivery;
use App\Domain\Catalog\CatalogType;
use App\Domain\Catalog\ReviewCatalogLookup;
use App\Infrastructure\Catalog\DeliveryCatalogSnapshotLoader;
use Illuminate\Console\Command;
use Throwable;

final class LookupDeliveredCatalogCommand extends Command
{
    protected $signature = 'atlas:catalog:lookup {delivery_sha256} {catalog} {version} {sha256} {--id= : Exact review catalog canonical ID}';

    protected $description = 'Load an exact delivered catalog from Atlas storage; no latest fallback or usage grant';

    public function handle(TransferAtlasDelivery $delivery, ReviewCatalogLookup $lookup): int
    {
        try {
            $type = CatalogType::from((string) $this->argument('catalog'));
            $loader = new DeliveryCatalogSnapshotLoader($delivery, (string) $this->argument('delivery_sha256'), [
                $type->value => ['version' => (string) $this->argument('version'), 'sha256' => (string) $this->argument('sha256')],
            ]);
            $snapshot = $loader->load($type);
            $counts = [];
            foreach ($snapshot->payload as $key => $value) {
                if (is_array($value) && array_is_list($value)) {
                    $counts[$key] = count($value);
                }
            }
            $result = ['catalog' => $type->value, 'version' => $snapshot->descriptor->version,
                'sha256' => $snapshot->descriptor->sha256, 'counts' => $counts, 'usage_allowed' => false, 'publish_allowed' => false];
            if (is_string($this->option('id'))) {
                $result['lookup'] = $lookup->lookup($snapshot, $this->option('id'));
            }
            $this->line(json_encode($result, JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));

            return self::SUCCESS;
        } catch (Throwable $exception) {
            $this->error($exception->getMessage());

            return self::FAILURE;
        }
    }
}
