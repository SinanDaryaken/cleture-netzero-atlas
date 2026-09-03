<?php

namespace App\Console\Commands;

use App\Application\Ingestion\AcquireSourceRelease;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use App\Domain\Ingestion\Exceptions\SourceTemporarilyUnavailable;
use Illuminate\Console\Command;
use InvalidArgumentException;
use LogicException;
use Throwable;

final class AcquireSourceReleaseCommand extends Command
{
    protected $signature = 'atlas:source:acquire {source : Source code, for example ADEME}';

    protected $description = 'Acquire and immutably store the latest raw source release';

    public function handle(AcquireSourceRelease $acquire): int
    {
        try {
            $result = $acquire->handle($this->argument('source'));
        } catch (InvalidArgumentException|LogicException|SourceContractViolation $exception) {
            $this->components->error($exception->getMessage());

            return self::INVALID;
        } catch (SourceTemporarilyUnavailable $exception) {
            $this->components->error($exception->getMessage());

            return self::FAILURE;
        } catch (Throwable $exception) {
            report($exception);
            $this->components->error('Source acquisition failed. See application logs for details.');

            return self::FAILURE;
        }

        $rawAsset = $result->rawAsset;
        $this->components->twoColumnDetail('Source', $result->release->sourceCode);
        $this->components->twoColumnDetail('Version', $result->release->version);
        $this->components->twoColumnDetail('Raw disk', $rawAsset->disk);
        $this->components->twoColumnDetail('Object key', $rawAsset->objectKey);
        $this->components->twoColumnDetail('SHA-256', $rawAsset->sha256);
        $this->components->twoColumnDetail('File size', number_format($rawAsset->fileSize).' bytes');
        $this->components->twoColumnDetail(
            'Outcome',
            $rawAsset->alreadyExisted ? 'already stored' : 'stored',
        );

        $this->newLine();
        $this->components->info('Raw acquisition completed; no parsing or canonical write was performed.');

        return self::SUCCESS;
    }
}
