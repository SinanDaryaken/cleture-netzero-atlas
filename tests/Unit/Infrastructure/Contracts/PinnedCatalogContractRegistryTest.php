<?php

namespace Tests\Unit\Infrastructure\Contracts;

use App\Domain\Catalog\CatalogContract;
use App\Domain\Catalog\CatalogContractDocument;
use App\Domain\Catalog\Exceptions\CatalogContractViolation;
use App\Infrastructure\Contracts\PinnedCatalogContractRegistry;
use Tests\TestCase;

final class PinnedCatalogContractRegistryTest extends TestCase
{
    public function test_loads_every_catalog_contract_with_verified_admin_provenance(): void
    {
        $registry = $this->registry();

        $documents = array_map($registry->get(...), CatalogContract::cases());

        $this->assertSame(
            CatalogContract::cases(),
            array_map(
                static fn (CatalogContractDocument $document): CatalogContract => $document->contract,
                $documents,
            ),
        );
        $this->assertSame(['1.0.0'], array_values(array_unique(array_column($documents, 'version'))));
        $this->assertSame(
            ['37a30fae4f68cbea24a981d4e975463a856ac0ee'],
            array_values(array_unique(array_column($documents, 'upstreamCommit'))),
        );
    }

    public function test_rejects_a_catalog_schema_when_its_bytes_change(): void
    {
        $directory = $this->temporaryContractDirectory();

        foreach (glob(base_path('resources/contracts/netzero-admin/catalog-v1/*')) ?: [] as $file) {
            copy($file, $directory.'/'.basename($file));
        }

        $schemaPath = $directory.'/atlas-catalog-unit-v1.schema.json';
        file_put_contents($schemaPath, file_get_contents($schemaPath)."\n");

        try {
            (new PinnedCatalogContractRegistry($directory.'/contract-manifest.json'))
                ->get(CatalogContract::Unit);
            $this->fail('A modified catalog schema was accepted.');
        } catch (CatalogContractViolation $exception) {
            $this->assertSame(
                'Pinned catalog contract unit failed integrity validation.',
                $exception->getMessage(),
            );
        } finally {
            $this->removeTemporaryDirectory($directory);
        }
    }

    private function registry(): PinnedCatalogContractRegistry
    {
        return new PinnedCatalogContractRegistry(
            base_path('resources/contracts/netzero-admin/catalog-v1/contract-manifest.json'),
        );
    }

    private function temporaryContractDirectory(): string
    {
        $directory = sys_get_temp_dir().'/atlas-catalog-contract-'.bin2hex(random_bytes(8));

        if (! mkdir($directory, 0700) && ! is_dir($directory)) {
            $this->fail('Temporary catalog contract directory could not be created.');
        }

        return $directory;
    }

    private function removeTemporaryDirectory(string $directory): void
    {
        foreach (glob($directory.'/*') ?: [] as $file) {
            unlink($file);
        }

        rmdir($directory);
    }
}
