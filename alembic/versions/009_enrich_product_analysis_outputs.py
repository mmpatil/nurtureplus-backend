"""Enrich product analysis outputs with website lookup metadata.

Revision ID: 009_enrich_product_analysis
Revises: 008_add_groups
Create Date: 2026-07-16 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "009_enrich_product_analysis"
down_revision = "008_add_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "product_analyses",
        sa.Column("lookup_status", sa.String(length=30), nullable=False, server_default="not_attempted"),
    )
    op.add_column(
        "product_analyses",
        sa.Column("category_guess", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "product_analyses",
        sa.Column("analysis_sources", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )

    op.alter_column(
        "product_suitability_assessments",
        "verdict",
        existing_type=sa.String(length=10),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.add_column(
        "product_suitability_assessments",
        sa.Column("headline", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "product_suitability_assessments",
        sa.Column(
            "ingredient_concerns",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "product_suitability_assessments",
        sa.Column(
            "category_concerns",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("product_suitability_assessments", "category_concerns")
    op.drop_column("product_suitability_assessments", "ingredient_concerns")
    op.drop_column("product_suitability_assessments", "headline")
    op.alter_column(
        "product_suitability_assessments",
        "verdict",
        existing_type=sa.String(length=20),
        type_=sa.String(length=10),
        existing_nullable=False,
    )

    op.drop_column("product_analyses", "analysis_sources")
    op.drop_column("product_analyses", "category_guess")
    op.drop_column("product_analyses", "lookup_status")
