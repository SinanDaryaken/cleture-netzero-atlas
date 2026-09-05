<?php

namespace App\Infrastructure\Candidate;

use App\Application\Candidate\CompareCandidateReleases;
use App\Application\Contracts\CandidateReleaseComparison;
use App\Domain\Candidate\CanonicalCandidateEntity;
use App\Domain\Candidate\Exceptions\CandidateContractViolation;
use PDO;

final readonly class DiskCandidateReleaseComparison implements CandidateReleaseComparison
{
    public function __construct(private CompareCandidateReleases $compare) {}

    public function compare(iterable $current, iterable $previous): iterable
    {
        $path = tempnam(sys_get_temp_dir(), 'atlas-diff-index-');
        if ($path === false) {
            throw new CandidateContractViolation('Cannot create diff index.');
        }
        try {
            $db = new PDO('sqlite:'.$path, options: [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
            $db->exec('PRAGMA cache_size = -2048');
            $db->exec('CREATE TABLE entities (side INTEGER, logical_key TEXT, variant_key TEXT, candidate_key TEXT, record TEXT, PRIMARY KEY (side, logical_key, variant_key), UNIQUE (side, candidate_key))');
            $insert = $db->prepare('INSERT INTO entities VALUES (?, ?, ?, ?, ?)');
            $db->beginTransaction();
            foreach ([$current, $previous] as $side => $entities) {
                foreach ($entities as $entity) {
                    $insert->execute([$side, $entity->record['logical_key'], $entity->record['variant_key'], $entity->candidateKey, $entity->canonicalJson]);
                }
            }
            $db->commit();
            $query = $db->query('SELECT logical_key, variant_key FROM entities GROUP BY logical_key, variant_key ORDER BY logical_key COLLATE BINARY, variant_key COLLATE BINARY');
            $lookup = $db->prepare('SELECT side, record FROM entities WHERE logical_key = ? AND variant_key = ?');
            while ($identity = $query->fetch(PDO::FETCH_ASSOC)) {
                $lookup->execute([$identity['logical_key'], $identity['variant_key']]);
                $pair = [[], []];
                foreach ($lookup->fetchAll(PDO::FETCH_ASSOC) as $row) {
                    $record = json_decode($row['record'], true, 512, JSON_THROW_ON_ERROR);
                    $pair[(int) $row['side']][] = new CanonicalCandidateEntity($record['candidate_key'], $record['record_sha256'], $record, $row['record']);
                }
                yield $this->compare->handle($pair[0], $pair[1])[0];
            }
        } finally {
            $lookup = $query = $insert = $db = null;
            unlink($path);
        }
    }
}
