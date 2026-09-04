<?php

namespace App\Console\Commands;

use App\Application\Candidate\NormalizeSourceRelease;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use Illuminate\Console\Command;
use InvalidArgumentException;
use LogicException;
use Throwable;

final class NormalizeSourceReleaseCommand extends Command
{
    protected $signature = 'atlas:source:normalize {source : Source code, for example ADEME}';

    protected $description = 'Normalize the latest parsed source release into candidate drafts';

    public function handle(NormalizeSourceRelease $normalize): int
    {
        try {
            $result = $normalize->handle($this->argument('source'));
        } catch (CandidateContractViolation|InvalidArgumentException|LogicException|SourceContractViolation $exception) {
            $this->components->error($exception->getMessage());

            return self::INVALID;
        } catch (Throwable $exception) {
            report($exception);
            $this->components->error('Source normalization failed. See application logs for details.');

            return self::FAILURE;
        }

        $artifact = $result->normalizedArtifact;
        $this->components->twoColumnDetail('Source', $result->input->sourceCode);
        $this->components->twoColumnDetail('Release', $result->input->releaseVersion);
        $this->components->twoColumnDetail('Normalizer version', $artifact->normalizerVersion);
        $this->components->twoColumnDetail('Candidate schema', $artifact->candidateSchemaVersion);
        $this->components->twoColumnDetail('Candidate drafts', number_format($artifact->candidateCount));
        $this->components->twoColumnDetail('Findings', number_format($artifact->findingCount));
        $this->components->twoColumnDetail('Processing disk', $artifact->disk);
        $this->components->twoColumnDetail('Object key', $artifact->objectKey);
        $this->components->twoColumnDetail('SHA-256', $artifact->sha256);
        $this->components->twoColumnDetail(
            'Outcome',
            $artifact->alreadyExisted ? 'already normalized' : 'normalized',
        );

        $this->newLine();
        $this->components->info('Normalization completed; no candidate package or canonical write was performed.');

        return self::SUCCESS;
    }
}
