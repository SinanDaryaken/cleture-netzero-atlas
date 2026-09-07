<?php

return [
    'current_approval' => [
        'enabled' => env('ATLAS_ADMIN_CURRENT_APPROVAL_ENABLED', false),
        'endpoint' => env('ATLAS_ADMIN_CURRENT_APPROVAL_ENDPOINT'),
        'key_id' => env('ATLAS_ADMIN_CURRENT_APPROVAL_KEY_ID'),
        'secret' => env('ATLAS_ADMIN_CURRENT_APPROVAL_SECRET'),
        'max_attempts' => (int) env('ATLAS_ADMIN_CURRENT_APPROVAL_MAX_ATTEMPTS', 2),
        'connect_timeout_seconds' => (int) env('ATLAS_ADMIN_CURRENT_APPROVAL_CONNECT_TIMEOUT_SECONDS', 3),
        'timeout_seconds' => (int) env('ATLAS_ADMIN_CURRENT_APPROVAL_TIMEOUT_SECONDS', 10),
    ],

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
        'candidate_disk' => env('ATLAS_CANDIDATES_DISK', 'atlas_candidates'),
        'catalog_disk' => env('ATLAS_CATALOG_DISK', 'atlas_catalogs'),
    ],

    'catalogs' => [
        'delivery' => [
            'sha256' => env('ATLAS_CATALOG_DELIVERY_SHA256'),
            'pins' => [
                'unit' => ['version' => env('ATLAS_DELIVERY_UNIT_VERSION'), 'sha256' => env('ATLAS_DELIVERY_UNIT_SHA256')],
                'geography' => ['version' => env('ATLAS_DELIVERY_GEOGRAPHY_VERSION'), 'sha256' => env('ATLAS_DELIVERY_GEOGRAPHY_SHA256')],
                'currency' => ['version' => env('ATLAS_DELIVERY_CURRENCY_VERSION'), 'sha256' => env('ATLAS_DELIVERY_CURRENCY_SHA256')],
                'taxonomy' => ['version' => env('ATLAS_DELIVERY_TAXONOMY_VERSION'), 'sha256' => env('ATLAS_DELIVERY_TAXONOMY_SHA256')],
                'intended_use' => ['version' => env('ATLAS_DELIVERY_INTENDED_USE_VERSION'), 'sha256' => env('ATLAS_DELIVERY_INTENDED_USE_SHA256')],
            ],
        ],
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
        'candidate_validation' => [
            'path' => base_path(env('ATLAS_CANDIDATE_VALIDATION_RULESET_PATH', 'resources/rules/candidate/validation-v1.json')),
            'sha256' => env('ATLAS_CANDIDATE_VALIDATION_RULESET_SHA256', '87f81981deda1e56d809b333133c7f338a8fd0acd3e780fb7cc4c6f1c249fc4c'),
        ],
        'candidate_mapping' => [
            'path' => base_path(env('ATLAS_CANDIDATE_MAPPING_RULESET_PATH', 'resources/rules/candidate/mapping-v1.json')),
            'sha256' => env('ATLAS_CANDIDATE_MAPPING_RULESET_SHA256', '4ee5673b66b8160f49c165c2e59384c53f9ceb7cf0550480e7b63a1e919405ba'),
        ],
        'candidate_diff' => [
            'path' => base_path(env(
                'ATLAS_CANDIDATE_DIFF_RULESET_PATH',
                'resources/rules/candidate/source-diff-v2.json',
            )),
            'sha256' => env(
                'ATLAS_CANDIDATE_DIFF_RULESET_SHA256',
                '46970a2946ac109b4f641b02e320a5375d8f0cd6135199603ea4a3dcf34aa303',
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
