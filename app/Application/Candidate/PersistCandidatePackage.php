<?php

namespace App\Application\Candidate;

use App\Application\Contracts\CandidatePackageLedger;
use App\Application\Contracts\CandidatePackageStorage;
use App\Domain\Candidate\CandidatePackageBuild;
use App\Domain\Candidate\CandidatePackageContext;
use App\Domain\Candidate\RegisteredCandidatePackage;

final readonly class PersistCandidatePackage
{
    public function __construct(
        private CandidatePackageStorage $storage,
        private CandidatePackageLedger $ledger,
    ) {}

    public function handle(
        CandidatePackageContext $context,
        CandidatePackageBuild $package,
    ): RegisteredCandidatePackage {
        $stored = $this->storage->store($package);

        return $this->ledger->register($context, $package, $stored);
    }
}
