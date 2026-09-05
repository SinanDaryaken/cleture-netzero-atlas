<?php

namespace App\Console\Commands;

use App\Application\Candidate\PrepareCandidatePackage;
use Illuminate\Console\Command;

final class BuildCandidatePackageCommand extends Command
{
    protected $signature = 'atlas:candidate:build {plan : Local versioned build-plan JSON path}';

    protected $description = 'Validate and persist a review candidate package from an explicitly selected normalized artifact';

    public function handle(PrepareCandidatePackage $prepare): int
    {
        try {
            $path = $this->argument('plan');
            if (! is_file($path)) {
                throw new \InvalidArgumentException('Build plan must be a local JSON file.');
            }
            $plan = json_decode(file_get_contents($path), true, 512, JSON_THROW_ON_ERROR);
            if (! is_array($plan)) {
                throw new \InvalidArgumentException('Build plan must be an object.');
            }
            $result = $prepare->handle($plan, config('atlas.storage.candidate_disk'));
            $this->components->twoColumnDetail('Validation identity', $result->validation->identity);
            $this->components->twoColumnDetail('Candidate dispositions', json_encode($result->validation->summary, JSON_THROW_ON_ERROR));
            if ($result->package === null) {
                $this->components->error('Package blocked; validation evidence was retained.');

                return self::INVALID;
            }
            $this->components->twoColumnDetail('Package ID', $result->package->packageId);
            $this->components->twoColumnDetail('Idempotency key', $result->package->idempotencyKey);
            $this->components->info('Candidate package persisted for review. Delivery remains a separate coordinated phase.');

            return self::SUCCESS;
        } catch (\Throwable $exception) {
            $this->components->error($exception->getMessage());

            return self::FAILURE;
        }
    }
}
