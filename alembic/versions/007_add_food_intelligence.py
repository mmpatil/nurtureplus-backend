"""Add backward-compatible food intelligence tables and feeding columns.

Revision ID: 007_add_food_intelligence
Revises: 006_add_caregiver_collaboration
Create Date: 2026-06-23 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "007_add_food_intelligence"
down_revision = "006_add_caregiver_collaboration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("feeding_entries", sa.Column("feeding_category", sa.String(length=50), nullable=True))
    op.add_column("feeding_entries", sa.Column("feeding_subtype", sa.String(length=50), nullable=True))
    op.add_column("feeding_entries", sa.Column("food_name", sa.String(length=255), nullable=True))
    op.add_column("feeding_entries", sa.Column("brand_name", sa.String(length=255), nullable=True))
    op.add_column("feeding_entries", sa.Column("amount_value", sa.Float(), nullable=True))
    op.add_column("feeding_entries", sa.Column("amount_unit", sa.String(length=30), nullable=True))
    op.add_column("feeding_entries", sa.Column("serving_count_offered", sa.Float(), nullable=True))
    op.add_column("feeding_entries", sa.Column("serving_count_consumed", sa.Float(), nullable=True))
    op.add_column("feeding_entries", sa.Column("consumed_fraction", sa.Float(), nullable=True))
    op.add_column("feeding_entries", sa.Column("analysis_status", sa.String(length=30), nullable=True))
    op.add_column("feeding_entries", sa.Column("analysis_confidence", sa.Float(), nullable=True))
    op.add_column("feeding_entries", sa.Column("nutrition_source", sa.String(length=30), nullable=True))

    op.execute(
        """
        UPDATE feeding_entries
        SET
            feeding_category = CASE
                WHEN feeding_type IN ('bottle', 'breast_left', 'breast_right', 'both') THEN 'milk_feed'
                ELSE feeding_category
            END,
            feeding_subtype = CASE
                WHEN feeding_type = 'bottle' THEN 'bottle_formula'
                WHEN feeding_type = 'breast_left' THEN 'breast_left'
                WHEN feeding_type = 'breast_right' THEN 'breast_right'
                WHEN feeding_type = 'both' THEN 'breast_both'
                ELSE feeding_subtype
            END
        """
    )

    op.create_table(
        "feeding_media",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "feeding_id",
            UUID(as_uuid=True),
            sa.ForeignKey("feeding_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "baby_id",
            UUID(as_uuid=True),
            sa.ForeignKey("babies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("media_role", sa.String(length=30), nullable=False),
        sa.Column("media_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_feeding_media_feeding_id", "feeding_media", ["feeding_id"])
    op.create_index("ix_feeding_media_baby_id", "feeding_media", ["baby_id"])
    op.create_index("ix_feeding_media_feeding_id_role", "feeding_media", ["feeding_id", "media_role"])

    op.create_table(
        "feeding_nutrition_estimates",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "feeding_id",
            UUID(as_uuid=True),
            sa.ForeignKey("feeding_entries.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "baby_id",
            UUID(as_uuid=True),
            sa.ForeignKey("babies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=30), nullable=True),
        sa.Column("calories", sa.Float(), nullable=True),
        sa.Column("protein_g", sa.Float(), nullable=True),
        sa.Column("fat_g", sa.Float(), nullable=True),
        sa.Column("carbs_g", sa.Float(), nullable=True),
        sa.Column("fiber_g", sa.Float(), nullable=True),
        sa.Column("sugar_g", sa.Float(), nullable=True),
        sa.Column("added_sugar_g", sa.Float(), nullable=True),
        sa.Column("sodium_mg", sa.Float(), nullable=True),
        sa.Column("iron_mg", sa.Float(), nullable=True),
        sa.Column("calcium_mg", sa.Float(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_feeding_nutrition_estimates_feeding_id",
        "feeding_nutrition_estimates",
        ["feeding_id"],
        unique=True,
    )
    op.create_index("ix_feeding_nutrition_estimates_baby_id", "feeding_nutrition_estimates", ["baby_id"])

    op.create_table(
        "baby_food_profiles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "baby_id",
            UUID(as_uuid=True),
            sa.ForeignKey("babies.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("allergens", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("avoid_ingredients", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("dietary_flags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("stage_override", sa.String(length=30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_baby_food_profiles_baby_id", "baby_food_profiles", ["baby_id"], unique=True)

    op.create_table(
        "product_analyses",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("product_name", sa.String(length=255), nullable=True),
        sa.Column("brand_name", sa.String(length=255), nullable=True),
        sa.Column("package_front_url", sa.Text(), nullable=True),
        sa.Column("package_back_url", sa.Text(), nullable=True),
        sa.Column("ingredients_text", sa.Text(), nullable=True),
        sa.Column("nutrition_facts_text", sa.Text(), nullable=True),
        sa.Column("parsed_facts", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_product_analyses_user_id", "product_analyses", ["user_id"])
    op.create_index(
        "ix_product_analyses_user_id_created_at",
        "product_analyses",
        ["user_id", "created_at"],
    )

    op.create_table(
        "product_suitability_assessments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "product_analysis_id",
            UUID(as_uuid=True),
            sa.ForeignKey("product_analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "baby_id",
            UUID(as_uuid=True),
            sa.ForeignKey("babies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("life_stage", sa.String(length=30), nullable=False),
        sa.Column("verdict", sa.String(length=10), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("warning_flags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("allergen_hits", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_product_suitability_assessments_product_analysis_id",
        "product_suitability_assessments",
        ["product_analysis_id"],
    )
    op.create_index(
        "ix_product_suitability_assessments_baby_id",
        "product_suitability_assessments",
        ["baby_id"],
    )
    op.create_index(
        "ix_product_suitability_assessments_product_analysis_baby",
        "product_suitability_assessments",
        ["product_analysis_id", "baby_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_suitability_assessments_product_analysis_baby",
        table_name="product_suitability_assessments",
    )
    op.drop_index(
        "ix_product_suitability_assessments_baby_id",
        table_name="product_suitability_assessments",
    )
    op.drop_index(
        "ix_product_suitability_assessments_product_analysis_id",
        table_name="product_suitability_assessments",
    )
    op.drop_table("product_suitability_assessments")

    op.drop_index("ix_product_analyses_user_id_created_at", table_name="product_analyses")
    op.drop_index("ix_product_analyses_user_id", table_name="product_analyses")
    op.drop_table("product_analyses")

    op.drop_index("ix_baby_food_profiles_baby_id", table_name="baby_food_profiles")
    op.drop_table("baby_food_profiles")

    op.drop_index(
        "ix_feeding_nutrition_estimates_baby_id",
        table_name="feeding_nutrition_estimates",
    )
    op.drop_index(
        "ix_feeding_nutrition_estimates_feeding_id",
        table_name="feeding_nutrition_estimates",
    )
    op.drop_table("feeding_nutrition_estimates")

    op.drop_index("ix_feeding_media_feeding_id_role", table_name="feeding_media")
    op.drop_index("ix_feeding_media_baby_id", table_name="feeding_media")
    op.drop_index("ix_feeding_media_feeding_id", table_name="feeding_media")
    op.drop_table("feeding_media")

    op.drop_column("feeding_entries", "nutrition_source")
    op.drop_column("feeding_entries", "analysis_confidence")
    op.drop_column("feeding_entries", "analysis_status")
    op.drop_column("feeding_entries", "consumed_fraction")
    op.drop_column("feeding_entries", "serving_count_consumed")
    op.drop_column("feeding_entries", "serving_count_offered")
    op.drop_column("feeding_entries", "amount_unit")
    op.drop_column("feeding_entries", "amount_value")
    op.drop_column("feeding_entries", "brand_name")
    op.drop_column("feeding_entries", "food_name")
    op.drop_column("feeding_entries", "feeding_subtype")
    op.drop_column("feeding_entries", "feeding_category")
