<?php

namespace App\Application\Contracts;

interface CanonicalJson
{
    public function encode(mixed $value): string;
}
