<?php

namespace App\Console\Commands;

use App\Application\Ingestion\PrepareSourceForAdmin;
use Illuminate\Console\Command;
use Throwable;

class PrepareSourceForAdminCommand extends Command
{
    protected $signature = 'atlas:source:prepare-admin {source : Source code, for example ADEME}';

    protected $description = 'Parse a source, match central references and store factors for Admin viewing';

    public function handle(PrepareSourceForAdmin $prepare): int
    {
        try {
            $result = $prepare->handle((string) $this->argument('source'));
        } catch (Throwable $exception) {
            report($exception);
            $this->components->error('Source preparation failed; no partial central import is visible. See application logs.');

            return self::FAILURE;
        }

        $this->components->twoColumnDetail('Import', $result['import_id']);
        $this->components->twoColumnDetail('Factors', (string) $result['record_count']);
        $this->components->info($result['already_existed'] ? 'Already available in Admin.' : 'Factors are available in Admin.');

        return self::SUCCESS;
    }
}
