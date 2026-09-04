<?php

namespace App\Domain\Ingestion;

use InvalidArgumentException;

final readonly class ParsedObservation
{
    /**
     * @param  array<string, string>  $fields
     */
    public function __construct(
        public int $sourceRow,
        public string $recordType,
        public string $sourceRecordId,
        public string $elementType,
        public string $status,
        public string $rowSha256,
        public array $fields,
    ) {
        if ($this->sourceRow < 1 || $this->recordType === '' || $this->sourceRecordId === '') {
            throw new InvalidArgumentException('Parsed observation identity is invalid.');
        }

        if (! preg_match('/^[a-f0-9]{64}$/', $this->rowSha256)) {
            throw new InvalidArgumentException('Parsed observation checksum must be a lowercase SHA-256 value.');
        }

        foreach ($this->fields as $name => $value) {
            if (! is_string($name) || ! is_string($value)) {
                throw new InvalidArgumentException('Parsed observation fields must contain string keys and values.');
            }
        }
    }
}
