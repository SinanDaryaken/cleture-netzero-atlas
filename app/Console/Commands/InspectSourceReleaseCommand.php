<?php

namespace App\Console\Commands;

use App\Application\Ingestion\InspectSourceRelease;
use App\Domain\Ingestion\Exceptions\SourceContractViolation;
use App\Domain\Ingestion\Exceptions\SourceTemporarilyUnavailable;
use Illuminate\Console\Command;
use InvalidArgumentException;

final class InspectSourceReleaseCommand extends Command
{
    protected $signature = 'atlas:source:inspect {source : Source code, for example ADEME}';

    protected $description = 'Inspect a source release without downloading or persisting it';

    public function handle(InspectSourceRelease $inspect): int
    {
        try {
            $release = $inspect->handle($this->argument('source'));
        } catch (InvalidArgumentException|SourceContractViolation $exception) {
            $this->components->error($exception->getMessage());

            return self::INVALID;
        } catch (SourceTemporarilyUnavailable $exception) {
            $this->components->error($exception->getMessage());

            return self::FAILURE;
        }

        $this->components->twoColumnDetail('Source', $release->sourceCode);
        $this->components->twoColumnDetail('Dataset', $release->datasetId);
        $this->components->twoColumnDetail('Version', $release->version);
        $this->components->twoColumnDetail('Reported rows', number_format($release->reportedRowCount));
        $this->components->twoColumnDetail('File', $release->fileName);
        $this->components->twoColumnDetail('File size', number_format($release->fileSize).' bytes');
        $this->components->twoColumnDetail('Upstream checksum', $release->upstreamChecksumAlgorithm.':'.$release->upstreamChecksum);
        $this->components->twoColumnDetail('Revision SHA-256', $release->revisionSha256);
        $this->components->twoColumnDetail('Source updated at', $release->sourceUpdatedAt?->format(DATE_ATOM) ?? 'unknown');
        $this->components->twoColumnDetail('License', $release->licenseTitle);
        $this->components->twoColumnDetail('Asset URL', $release->assetUrl);

        $this->newLine();
        $this->components->info('Inspection completed without downloading or persisting source data.');

        return self::SUCCESS;
    }
}
