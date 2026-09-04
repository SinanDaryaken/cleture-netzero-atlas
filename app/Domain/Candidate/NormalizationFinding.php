<?php

namespace App\Domain\Candidate;

use InvalidArgumentException;

final readonly class NormalizationFinding
{
    /** @param array<string, string|int|bool|null> $context */
    public function __construct(
        public string $code,
        public string $severity,
        public string $candidateKey,
        public string $message,
        public array $context = [],
    ) {
        if ($this->code === '' || $this->candidateKey === '' || $this->message === '') {
            throw new InvalidArgumentException('Normalization finding identity cannot be empty.');
        }

        if (! in_array($this->severity, ['warning', 'review', 'blocking'], true)) {
            throw new InvalidArgumentException('Normalization finding severity is invalid.');
        }
    }
}
