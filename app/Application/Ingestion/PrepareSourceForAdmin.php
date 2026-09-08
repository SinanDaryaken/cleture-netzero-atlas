<?php

namespace App\Application\Ingestion;

use App\Application\Candidate\NormalizeSourceRelease;
use App\Infrastructure\Persistence\CentralFactorWriter;

class PrepareSourceForAdmin
{
    public function __construct(
        private AcquireSourceRelease $acquire,
        private ParseSourceRelease $parse,
        private NormalizeSourceRelease $normalize,
        private CentralFactorWriter $writer,
    ) {}

    /** @return array{import_id: string, record_count: int, already_existed: bool} */
    public function handle(string $source): array
    {
        $source = mb_strtoupper(trim($source));
        if (! $this->writer->supports($source)) {
            throw new \InvalidArgumentException('This source is not supported by the Admin preparation flow yet.');
        }
        $this->writer->ensureAvailable();
        $this->acquire->handle($source);
        $this->parse->handle($source);

        return $this->writer->write($this->normalize->handle($source));
    }
}
