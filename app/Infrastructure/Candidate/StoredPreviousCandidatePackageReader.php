<?php

namespace App\Infrastructure\Candidate;

use App\Application\Contracts\CandidateSchemaValidator;
use App\Application\Contracts\PreviousCandidatePackageReader;
use App\Domain\Candidate\CandidateArchiveMember;
use App\Domain\Candidate\CandidateContract;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use App\Infrastructure\Persistence\Models\CandidatePackageRecord;
use Illuminate\Filesystem\FilesystemManager;
use ZipArchive;

final readonly class StoredPreviousCandidatePackageReader implements PreviousCandidatePackageReader
{
    public function __construct(private FilesystemManager $filesystems, private CandidateSchemaValidator $schemas) {}

    public function entities(string $packageId, array $source): CandidateArchiveMember
    {
        $record = CandidatePackageRecord::query()->findOrFail($packageId);
        $filesystem = $this->filesystems->disk($record->disk);
        $bytes = $filesystem->get($record->manifest_object_key);
        if (strlen($bytes) !== $record->manifest_size || ! hash_equals($record->manifest_sha256, hash('sha256', $bytes))) {
            throw new CandidateContractViolation('Previous manifest checksum mismatch.');
        }
        $manifest = json_decode($bytes, true, 512, JSON_THROW_ON_ERROR);
        $this->schemas->assertValid(CandidateContract::PackageManifest, get_object_vars(json_decode($bytes, false, 512, JSON_THROW_ON_ERROR)));
        if ($manifest['package_id'] !== $packageId || $manifest['source']['code'] !== $source['code'] || $manifest['source']['dataset_id'] !== $source['dataset_id']
            || $manifest['artifact']['sha256'] !== $record->archive_sha256 || $manifest['artifact']['object_key'] !== $record->archive_object_key) {
            throw new CandidateContractViolation('Previous package identity or source mismatch.');
        }
        $archive = tempnam(sys_get_temp_dir(), 'atlas-previous-zip-');
        $entities = tempnam(sys_get_temp_dir(), 'atlas-previous-entities-');
        if ($archive === false || $entities === false) {
            throw new CandidateContractViolation('Cannot create previous package workspace.');
        }
        $zip = new ZipArchive;
        $opened = false;
        try {
            $input = $filesystem->readStream($record->archive_object_key);
            $output = fopen($archive, 'wb');
            if (! is_resource($input) || ! is_resource($output)) {
                throw new CandidateContractViolation('Previous archive is unavailable.');
            }
            try {
                stream_copy_to_stream($input, $output);
            } finally {
                fclose($input);
                fclose($output);
            }
            if (filesize($archive) !== $record->archive_size || ! hash_equals($record->archive_sha256, hash_file('sha256', $archive))) {
                throw new CandidateContractViolation('Previous archive checksum mismatch.');
            }
            $opened = $zip->open($archive) === true;
            if (! $opened || $zip->numFiles !== 4) {
                throw new CandidateContractViolation('Previous archive members are invalid.');
            }
            $input = $zip->getStream('entities.ndjson');
            $output = fopen($entities, 'wb');
            if (! is_resource($input)) {
                fclose($output);
                throw new CandidateContractViolation('Previous entity member is absent.');
            }
            try {
                stream_copy_to_stream($input, $output);
            } finally {
                fclose($input);
                fclose($output);
            }
            $member = $manifest['members']['entities'];

            return new CandidateArchiveMember('entities.ndjson', $entities, $member['sha256'], $member['size_bytes'], $member['record_count']);
        } catch (\Throwable $exception) {
            unlink($entities);
            throw $exception;
        } finally {
            if ($opened) {
                $zip->close();
            }
            unlink($archive);
        }
    }
}
