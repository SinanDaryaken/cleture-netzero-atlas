<?php

namespace App\Console\Commands;

use App\Application\Catalog\TransferAtlasDelivery;
use App\Infrastructure\Catalog\LocalDeliveryDirectory;
use App\Infrastructure\Catalog\VerifyAtlasDelivery;
use Illuminate\Console\Command;
use Throwable;

final class AtlasDeliveryCommand extends Command
{
    protected $signature = 'atlas:catalog:delivery {sha256 : Independently trusted manifest hash}
        {--source= : Exact local delivery directory; absent reads the real target}
        {--transfer : Transfer source to configured Atlas catalog disk, then read back}';

    protected $description = 'Verify or provision exact catalog delivery; never grants current approval or publication';

    public function handle(TransferAtlasDelivery $transfer, VerifyAtlasDelivery $verify): int
    {
        try {
            $hash = (string) $this->argument('sha256');
            $source = $this->option('source');
            if ($this->option('transfer') && ! is_string($source)) {
                throw new \InvalidArgumentException('Transfer requires an explicit source directory.');
            }
            $result = is_string($source)
                ? ($this->option('transfer')
                    ? $transfer->transfer($hash, (new LocalDeliveryDirectory($source))->read(...))
                    : $verify->verify($hash, (new LocalDeliveryDirectory($source))->read(...)))
                : $transfer->read($hash);
            $receipt = $result->receipt();
            $receipt['read_from'] = is_string($source) && ! $this->option('transfer') ? 'local_source_only' : config('atlas.storage.catalog_disk');
            $this->line(json_encode($receipt, JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));

            return self::SUCCESS;
        } catch (Throwable $exception) {
            $this->error($exception->getMessage());

            return self::FAILURE;
        }
    }
}
