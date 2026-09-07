<?php

namespace App\Console\Commands;

use App\Application\Catalog\CheckDeliveredResolutionApproval;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use App\Domain\Catalog\SortedCatalogJson;
use Illuminate\Console\Command;
use Throwable;

final class AtlasCurrentApprovalCommand extends Command
{
    protected $signature = 'atlas:catalog:current-approval {sha256 : Independently trusted delivery SHA}
        {expected : File containing the exact independently expected resolution envelope}
        {--require-for-use : Evaluate the final usage gate, which remains blocked in v1}';

    protected $description = 'Read the stored delivery and query current approval; grants no mapping, usage or publication';

    public function handle(CheckDeliveredResolutionApproval $check, SortedCatalogJson $json): int
    {
        try {
            $path = (string) $this->argument('expected');
            if (! is_file($path)) {
                throw new CatalogContractViolation('Expected resolution must be an explicit local file.');
            }
            $bytes = @file_get_contents($path, false, null, 0, 16385);
            if (! is_string($bytes) || strlen($bytes) > 16384) {
                throw new CatalogContractViolation('Expected resolution file is unavailable or exceeds its byte limit.');
            }
            $expected = $json->decode($bytes);
            $hash = (string) $this->argument('sha256');
            if ($this->option('require-for-use')) {
                $check->requireForUse($hash, $expected);
            }
            $this->line(json_encode($check->inspect($hash, $expected)->receipt(), JSON_THROW_ON_ERROR | JSON_PRETTY_PRINT));

            return self::SUCCESS;
        } catch (Throwable $exception) {
            $this->error($exception->getMessage());

            return self::FAILURE;
        }
    }
}
