"""Alembic migration 0021: LGD reference tables and seed data.

Creates lgd_states, lgd_districts, lgd_markets, lgd_commodities,
lgd_market_aliases, and lgd_unresolved tables in schema ``app``.

Seeds reference data from ``app/data/lgd_seed.json`` covering the 12 major
agricultural states (MH, KA, MP, UP, GJ, RJ, PB, HR, TN, TS, AP, WB) with
their districts, top mandis, and key commodity classifications.

Data source: Local Government Directory (lgd.gov.in), snapshot 2026-08-01.

Revision ID: 0021_lgd_reference_data
Revises: 0020_assay_ai_models
Create Date: 2026-09-25
"""

import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0021_lgd_reference_data"
down_revision = "0020_assay_ai_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── lgd_states ──
    op.create_table(
        "lgd_states",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("state_code", sa.String(4), nullable=False),
        sa.Column("state_name", sa.String(128), nullable=False),
        sa.Column("lgd_code", sa.String(8), nullable=False),
        sa.UniqueConstraint("lgd_code", name="uq_lgd_states_lgd_code"),
        sa.UniqueConstraint("state_code", name="uq_lgd_states_state_code"),
        schema="app",
    )

    # ── lgd_districts ──
    op.create_table(
        "lgd_districts",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("district_name", sa.String(128), nullable=False),
        sa.Column("lgd_code", sa.String(8), nullable=False),
        sa.Column("state_lgd_code", sa.String(8), nullable=False),
        sa.UniqueConstraint("lgd_code", name="uq_lgd_districts_lgd_code"),
        schema="app",
    )
    op.create_index(
        "ix_lgd_districts_state_lgd_code",
        "lgd_districts",
        ["state_lgd_code"],
        schema="app",
    )

    # ── lgd_markets ──
    op.create_table(
        "lgd_markets",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("market_name", sa.String(256), nullable=False),
        sa.Column("district_lgd_code", sa.String(8), nullable=False),
        sa.Column("state_lgd_code", sa.String(8), nullable=False),
        sa.Column("lat", sa.Float),
        sa.Column("lon", sa.Float),
        schema="app",
    )
    op.create_index(
        "ix_lgd_markets_district_lgd_code",
        "lgd_markets",
        ["district_lgd_code"],
        schema="app",
    )
    op.create_index(
        "ix_lgd_markets_state_lgd_code",
        "lgd_markets",
        ["state_lgd_code"],
        schema="app",
    )

    # ── lgd_commodities ──
    op.create_table(
        "lgd_commodities",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("commodity_name", sa.String(128), nullable=False),
        sa.Column("group_name", sa.String(128)),
        sa.Column("grade", sa.String(64), nullable=False, server_default="FAQ"),
        sa.Column("standard_code", sa.String(32)),
        sa.UniqueConstraint("commodity_name", "grade", name="uq_lgd_commodities_name_grade"),
        schema="app",
    )

    # ── lgd_market_aliases ──
    op.create_table(
        "lgd_market_aliases",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("raw_name", sa.String(256), nullable=False),
        sa.Column("market_id", sa.BigInteger, nullable=False),
        sa.Column("created_by", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("raw_name", name="uq_lgd_market_aliases_raw_name"),
        schema="app",
    )
    op.create_index(
        "ix_lgd_market_aliases_market_id",
        "lgd_market_aliases",
        ["market_id"],
        schema="app",
    )

    # ── lgd_unresolved ──
    op.create_table(
        "lgd_unresolved",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("raw_name", sa.String(256), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("state_hint", sa.String(128)),
        sa.Column("district_hint", sa.String(128)),
        sa.Column("best_guess_lgd_code", sa.String(8)),
        sa.Column("confidence", sa.Float),
        sa.Column("resolution_method", sa.String(32)),
        sa.Column("resolved", sa.Boolean, server_default=sa.text("false")),
        sa.Column("resolved_lgd_code", sa.String(8)),
        sa.Column("resolved_by", sa.String(128)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("occurrence_count", sa.Integer, server_default="1"),
        sa.UniqueConstraint("raw_name", "entity_type", name="uq_lgd_unresolved_raw_name_type"),
        schema="app",
    )

    # ── Add lgd_market_id + lgd_commodity_id FK columns to price_observations ──
    op.add_column(
        "price_observations",
        sa.Column("lgd_market_id", sa.BigInteger, nullable=True),
        schema="app",
    )
    op.add_column(
        "price_observations",
        sa.Column("lgd_commodity_id", sa.BigInteger, nullable=True),
        schema="app",
    )
    op.add_column(
        "price_observations",
        sa.Column("lgd_resolution_method", sa.String(32), nullable=True),
        schema="app",
    )
    op.add_column(
        "price_observations",
        sa.Column("lgd_resolution_confidence", sa.Float, nullable=True),
        schema="app",
    )

    # ── Seed reference data ──
    seed_path = Path(__file__).resolve().parents[1] / "app" / "data" / "lgd_seed.json"
    if seed_path.exists():
        seed = json.loads(seed_path.read_text(encoding="utf-8"))

        states_table = sa.table(
            "lgd_states",
            sa.column("state_code", sa.String),
            sa.column("state_name", sa.String),
            sa.column("lgd_code", sa.String),
            schema="app",
        )
        for s in seed.get("states", []):
            op.execute(
                states_table.insert().values(
                    state_code=s["state_code"],
                    state_name=s["state_name"],
                    lgd_code=s["lgd_code"],
                )
            )

        districts_table = sa.table(
            "lgd_districts",
            sa.column("district_name", sa.String),
            sa.column("lgd_code", sa.String),
            sa.column("state_lgd_code", sa.String),
            schema="app",
        )
        for d in seed.get("districts", []):
            op.execute(
                districts_table.insert().values(
                    district_name=d["district_name"],
                    lgd_code=d["lgd_code"],
                    state_lgd_code=d["state_lgd_code"],
                )
            )

        markets_table = sa.table(
            "lgd_markets",
            sa.column("market_name", sa.String),
            sa.column("district_lgd_code", sa.String),
            sa.column("state_lgd_code", sa.String),
            sa.column("lat", sa.Float),
            sa.column("lon", sa.Float),
            schema="app",
        )
        for m in seed.get("markets", []):
            op.execute(
                markets_table.insert().values(
                    market_name=m["market_name"],
                    district_lgd_code=m["district_lgd_code"],
                    state_lgd_code=m["state_lgd_code"],
                    lat=m.get("lat"),
                    lon=m.get("lon"),
                )
            )

        commodities_table = sa.table(
            "lgd_commodities",
            sa.column("commodity_name", sa.String),
            sa.column("group_name", sa.String),
            sa.column("grade", sa.String),
            sa.column("standard_code", sa.String),
            schema="app",
        )
        for c in seed.get("commodities", []):
            op.execute(
                commodities_table.insert().values(
                    commodity_name=c["commodity_name"],
                    group_name=c.get("group"),
                    grade=c.get("grade", "FAQ"),
                    standard_code=c.get("standard_code"),
                )
            )


def downgrade() -> None:
    op.drop_column("price_observations", "lgd_resolution_confidence", schema="app")
    op.drop_column("price_observations", "lgd_resolution_method", schema="app")
    op.drop_column("price_observations", "lgd_commodity_id", schema="app")
    op.drop_column("price_observations", "lgd_market_id", schema="app")
    op.drop_table("lgd_unresolved", schema="app")
    op.drop_index("ix_lgd_market_aliases_market_id", table_name="lgd_market_aliases", schema="app")
    op.drop_table("lgd_market_aliases", schema="app")
    op.drop_table("lgd_commodities", schema="app")
    op.drop_index("ix_lgd_markets_state_lgd_code", table_name="lgd_markets", schema="app")
    op.drop_index("ix_lgd_markets_district_lgd_code", table_name="lgd_markets", schema="app")
    op.drop_table("lgd_markets", schema="app")
    op.drop_index("ix_lgd_districts_state_lgd_code", table_name="lgd_districts", schema="app")
    op.drop_table("lgd_districts", schema="app")
    op.drop_table("lgd_states", schema="app")
