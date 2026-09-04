<?php

namespace App\Console\Commands;

use App\Application\Ingestion\ParseSourceRelease;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use Illuminate\Console\Command;
use InvalidArgumentException;
use LogicException;
use Throwable;

final class ParseSourceReleaseCommand extends Command
{
    protected $signature = 'atlas:source:parse {source : Source code, for example ADEME}';

    protected $description = 'Parse the latest immutable raw source release into observations';

    public function handle(ParseSourceRelease $parse): int
    {
        try {
            $result = $parse->handle($this->argument('source'));
        } catch (InvalidArgumentException|LogicException|SourceContractViolation $exception) {
            $this->components->error($exception->getMessage());

            return self::INVALID;
        } catch (Throwable $exception) {
            report($exception);
            $this->components->error('Source parsing failed. See application logs for details.');

            return self::FAILURE;
        }

        $artifact = $result->parsedArtifact;
        $this->components->twoColumnDetail('Source', $result->rawAsset->sourceCode);
        $this->components->twoColumnDetail('Release', $result->rawAsset->releaseVersion);
        $this->components->twoColumnDetail('Parser version', $artifact->parserVersion);
        $this->components->twoColumnDetail('Schema version', $artifact->schemaVersion);
        $this->components->twoColumnDetail('Source encoding', $artifact->sourceEncoding);
        $this->components->twoColumnDetail('Parsed rows', number_format($artifact->rowCount));
        $this->components->twoColumnDetail('Processing disk', $artifact->disk);
        $this->components->twoColumnDetail('Object key', $artifact->objectKey);
        $this->components->twoColumnDetail('SHA-256', $artifact->sha256);
        $this->components->twoColumnDetail(
            'Outcome',
            $artifact->alreadyExisted ? 'already parsed' : 'parsed',
        );

        $this->newLine();
        $this->components->info('Parsing completed; no normalization or canonical write was performed.');

        return self::SUCCESS;
    }
}
