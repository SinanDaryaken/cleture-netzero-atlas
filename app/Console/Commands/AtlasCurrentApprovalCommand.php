<?php

namespace App\Console\Commands;

use App\Application\Catalog\CheckDeliveredResolutionApproval;
use App\Infrastructure\Catalog\ExpectedResolutionFile;
use Illuminate\Console\Command;
use Throwable;

final class AtlasCurrentApprovalCommand extends Command
{
    protected $signature = 'atlas:catalog:current-approval {sha256 : Independently trusted delivery SHA}
        {expected : File containing the exact independently expected resolution envelope}
        {--require-for-use : Evaluate the final usage gate, which remains blocked in v1}';

    protected $description = 'Read the stored delivery and query current approval; grants no mapping, usage or publication';

    public function handle(CheckDeliveredResolutionApproval $check, ExpectedResolutionFile $files): int
    {
        try {
            $expected = $files->read((string) $this->argument('expected'));
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
