<?php

use App\Application\Candidate\PrepareCandidatePackage;
use Illuminate\Contracts\Console\Kernel;

require __DIR__.'/../../vendor/autoload.php';

$app = require __DIR__.'/../../bootstrap/app.php';
$app->make(Kernel::class)->bootstrap();
$input = json_decode(file_get_contents($argv[1]), true, 512, JSON_THROW_ON_ERROR);
config(['atlas.catalogs.snapshots' => $input['catalogs']]);
foreach (['atlas_processing', 'atlas_catalogs', 'atlas_candidates'] as $disk) {
    config(["filesystems.disks.{$disk}.bucket" => $input['bucket']]);
}
try {
    $result = $app->make(PrepareCandidatePackage::class)->handle($input['plan'], 'atlas_candidates');
    echo json_encode(['package' => $result->package->packageId, 'manifest' => $result->package->storage->manifestSha256], JSON_THROW_ON_ERROR);
} catch (Throwable $exception) {
    fwrite(STDERR, $exception::class.': '.$exception->getMessage());
    exit(1);
}
