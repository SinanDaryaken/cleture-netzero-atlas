<?php

return [
    'storage' => [
        'raw_disk' => env('ATLAS_RAW_DISK', 'atlas_raw'),
        'processing_disk' => env('ATLAS_PROCESSING_DISK', 'atlas_processing'),
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
