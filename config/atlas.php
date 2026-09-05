<?php

return [
    'contracts' => [
        'candidate_manifest_path' => base_path(
            'resources/contracts/netzero-admin/candidate-v2/contract-manifest.json',
        ),
        'candidate_v1_manifest_path' => base_path(
            'resources/contracts/netzero-admin/candidate-v1/contract-manifest.json',
        ),
        'candidate_v2_manifest_path' => base_path(
            'resources/contracts/netzero-admin/candidate-v2/contract-manifest.json',
        ),
        'catalog_manifest_path' => base_path(
            'resources/contracts/netzero-admin/catalog-v1/contract-manifest.json',
        ),
    ],

    'storage' => [
        'raw_disk' => env('ATLAS_RAW_DISK', 'atlas_raw'),
        'processing_disk' => env('ATLAS_PROCESSING_DISK', 'atlas_processing'),
        'catalog_disk' => env('ATLAS_CATALOG_DISK', 'atlas_catalogs'),
    ],

    'catalogs' => [
        'snapshots' => [
            'geography' => [
                'descriptor_path' => env(
                    'ATLAS_GEOGRAPHY_CATALOG_DESCRIPTOR_PATH',
                    'atlas-catalog-snapshots/geography/sha256/'
                    .'63e4c102f3622f48c746a7a1144a3e07d6d64ee519940acb66c38289bdc36ac8.json.manifest.json',
                ),
                'descriptor_sha256' => env(
                    'ATLAS_GEOGRAPHY_CATALOG_DESCRIPTOR_SHA256',
                    '61f46ebde57abba344009d24047b0baaeb6e7cd185ffaf0444d39b762f07eb7f',
                ),
            ],
            'unit' => [
                'descriptor_path' => env(
                    'ATLAS_UNIT_CATALOG_DESCRIPTOR_PATH',
                    'atlas-catalog-snapshots/unit/sha256/'
                    .'dfd210dfe04c0bc2dcf613e140637c249e1be76fc5d58a98efffeab73f99ddf3.json.manifest.json',
                ),
                'descriptor_sha256' => env(
                    'ATLAS_UNIT_CATALOG_DESCRIPTOR_SHA256',
                    '9037b58b2612b720100b473d4cf8b0e6bf909c3fd42ae9958f312cf6e90a210e',
                ),
            ],
        ],
    ],

    'rulesets' => [
        'candidate_diff' => [
            'path' => base_path(env(
                'ATLAS_CANDIDATE_DIFF_RULESET_PATH',
                'resources/rules/candidate/source-diff-v1.json',
            )),
            'sha256' => env(
                'ATLAS_CANDIDATE_DIFF_RULESET_SHA256',
                'ec6976b14a1a761f5bc0b143db216ec13605e522b6bdab3d7f99646a9546b740',
            ),
        ],
    ],

    'http' => [
        'connect_timeout_seconds' => (int) env('ATLAS_HTTP_CONNECT_TIMEOUT_SECONDS', 10),
        'timeout_seconds' => (int) env('ATLAS_HTTP_TIMEOUT_SECONDS', 30),
    ],

    'sources' => [
        'ademe' => [
            'dataset_url' => env(
                'ATLAS_ADEME_DATASET_URL',
                'https://data.ademe.fr/data-fair/api/v1/datasets/base-carboner',
            ),
        ],
    ],
];
