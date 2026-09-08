<?php

namespace Tests\Feature;

use App\Application\Ingestion\PrepareSourceForAdmin;
use Illuminate\Support\Facades\Artisan;
use Tests\TestCase;

class RetiredTransportTest extends TestCase
{
    public function test_direct_preparation_resolves_without_delivery_or_package_services(): void
    {
        $this->assertInstanceOf(PrepareSourceForAdmin::class, $this->app->make(PrepareSourceForAdmin::class));
        $commands = Artisan::all();
        $this->assertArrayHasKey('atlas:source:prepare-admin', $commands);
        foreach (array_keys($commands) as $name) {
            $this->assertDoesNotMatchRegularExpression('/^atlas:.*(?:delivery|approval|package|lookup)/', $name);
        }
    }
}
