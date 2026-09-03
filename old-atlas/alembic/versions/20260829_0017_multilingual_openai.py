"""Add reviewed terminology, glossary and OpenAI translation jobs.

Revision ID: 20260829_0017
Revises: 20260829_0016
Create Date: 2026-08-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260829_0017"
down_revision: str | None = "20260829_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE atlas_concepts
          ADD COLUMN definition_en TEXT,
          ADD COLUMN english_review_status VARCHAR(32) NOT NULL DEFAULT 'unreviewed',
          ADD COLUMN english_reviewed_by VARCHAR(255),
          ADD COLUMN english_reviewed_at TIMESTAMPTZ;
        CREATE INDEX ix_atlas_concepts_english_review_status
          ON atlas_concepts (english_review_status);

        ALTER TABLE atlas_concept_labels
          ADD COLUMN locale VARCHAR(16),
          ADD COLUMN definition TEXT,
          ADD COLUMN is_preferred BOOLEAN NOT NULL DEFAULT FALSE,
          ADD COLUMN term_source VARCHAR(64) NOT NULL DEFAULT 'registry',
          ADD COLUMN prompt_version VARCHAR(64),
          ADD COLUMN glossary_version VARCHAR(64),
          ADD COLUMN tokens JSONB NOT NULL DEFAULT '[]'::jsonb,
          ADD COLUMN transliteration VARCHAR(255),
          ADD COLUMN qa_flags JSONB NOT NULL DEFAULT '[]'::jsonb,
          ADD COLUMN supersedes_id UUID REFERENCES atlas_concept_labels(id) ON DELETE SET NULL;
        UPDATE atlas_concept_labels
           SET is_preferred = label_kind IN ('canonical', 'translation')
         WHERE review_status = 'approved';
        CREATE INDEX ix_atlas_concept_labels_locale ON atlas_concept_labels (locale);
        CREATE INDEX ix_atlas_concept_labels_is_preferred ON atlas_concept_labels (is_preferred);
        CREATE INDEX ix_atlas_concept_labels_prompt_version
          ON atlas_concept_labels (prompt_version);
        CREATE INDEX ix_atlas_concept_labels_glossary_version
          ON atlas_concept_labels (glossary_version);
        CREATE INDEX ix_atlas_concept_labels_transliteration
          ON atlas_concept_labels (transliteration);
        CREATE INDEX ix_atlas_concept_labels_supersedes_id
          ON atlas_concept_labels (supersedes_id);

        CREATE TABLE atlas_translation_jobs (
          id UUID PRIMARY KEY,
          provider VARCHAR(64) NOT NULL,
          provider_job_id VARCHAR(255) UNIQUE,
          input_file_id VARCHAR(255),
          output_file_id VARCHAR(255),
          error_file_id VARCHAR(255),
          source_language VARCHAR(8) NOT NULL,
          target_language VARCHAR(8) NOT NULL,
          model VARCHAR(255) NOT NULL,
          qa_model VARCHAR(255),
          prompt_version VARCHAR(64) NOT NULL,
          glossary_version VARCHAR(64),
          status VARCHAR(32) NOT NULL DEFAULT 'created',
          requested_count INTEGER NOT NULL DEFAULT 0,
          completed_count INTEGER NOT NULL DEFAULT 0,
          failed_count INTEGER NOT NULL DEFAULT 0,
          custom_ids JSONB NOT NULL DEFAULT '{}'::jsonb,
          error TEXT,
          requested_by VARCHAR(255) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_atlas_translation_jobs_provider ON atlas_translation_jobs (provider);
        CREATE INDEX ix_atlas_translation_jobs_provider_job_id
          ON atlas_translation_jobs (provider_job_id);
        CREATE INDEX ix_atlas_translation_jobs_target_language
          ON atlas_translation_jobs (target_language);
        CREATE INDEX ix_atlas_translation_jobs_prompt_version
          ON atlas_translation_jobs (prompt_version);
        CREATE INDEX ix_atlas_translation_jobs_glossary_version
          ON atlas_translation_jobs (glossary_version);
        CREATE INDEX ix_atlas_translation_jobs_status ON atlas_translation_jobs (status);

        CREATE TABLE atlas_translation_glossary (
          id UUID PRIMARY KEY,
          source_term VARCHAR(255) NOT NULL,
          target_language VARCHAR(8) NOT NULL,
          target_term VARCHAR(255),
          domain VARCHAR(128) NOT NULL DEFAULT 'environmental',
          protected BOOLEAN NOT NULL DEFAULT FALSE,
          review_status VARCHAR(32) NOT NULL DEFAULT 'approved',
          version VARCHAR(64) NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          CONSTRAINT uq_atlas_translation_glossary
            UNIQUE (source_term, target_language, domain)
        );
        CREATE INDEX ix_atlas_translation_glossary_source_term
          ON atlas_translation_glossary (source_term);
        CREATE INDEX ix_atlas_translation_glossary_target_language
          ON atlas_translation_glossary (target_language);
        CREATE INDEX ix_atlas_translation_glossary_review_status
          ON atlas_translation_glossary (review_status);
        CREATE INDEX ix_atlas_translation_glossary_version
          ON atlas_translation_glossary (version);

        INSERT INTO atlas_translation_glossary (
          id, source_term, target_language, target_term, domain,
          protected, review_status, version
        )
        SELECT md5(source_term || ':' || target_language)::uuid,
               source_term, target_language, NULL, 'environmental',
               TRUE, 'approved', '1.0.0'
          FROM unnest(ARRAY['CO2e', 'GHG Protocol', 'CBAM', 'Scope 1', 'Scope 2', 'IPCC'])
               AS source_terms(source_term)
         CROSS JOIN unnest(ARRAY['en', 'tr', 'de', 'fr', 'es', 'ru', 'ar'])
               AS languages(target_language);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS atlas_translation_glossary;
        DROP TABLE IF EXISTS atlas_translation_jobs;
        ALTER TABLE atlas_concept_labels
          DROP COLUMN IF EXISTS supersedes_id,
          DROP COLUMN IF EXISTS qa_flags,
          DROP COLUMN IF EXISTS transliteration,
          DROP COLUMN IF EXISTS tokens,
          DROP COLUMN IF EXISTS glossary_version,
          DROP COLUMN IF EXISTS prompt_version,
          DROP COLUMN IF EXISTS term_source,
          DROP COLUMN IF EXISTS is_preferred,
          DROP COLUMN IF EXISTS definition,
          DROP COLUMN IF EXISTS locale;
        ALTER TABLE atlas_concepts
          DROP COLUMN IF EXISTS english_reviewed_at,
          DROP COLUMN IF EXISTS english_reviewed_by,
          DROP COLUMN IF EXISTS english_review_status,
          DROP COLUMN IF EXISTS definition_en;
        """
    )
