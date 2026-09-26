"""create ONDC v2.0.0, IGM, Ratings, TLC, and BAP tables

Revision ID: 0018_ondc_v2_and_bap
Revises: 0017_kafka_outbox_relay_and_consumer
Create Date: 2026-09-25

"""

import sqlalchemy as sa
from alembic import op

revision = "0018_ondc_v2_and_bap"
down_revision = "0017_kafka_outbox_relay_and_consumer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Extend trade_contracts with BAP/BPP unified role and TLC hash
    op.add_column("trade_contracts", sa.Column("bap_id", sa.String(128), nullable=True), schema="app")
    op.add_column("trade_contracts", sa.Column("bpp_id", sa.String(128), nullable=True), schema="app")
    op.add_column("trade_contracts", sa.Column("role", sa.String(16), nullable=True, server_default="BPP"), schema="app")
    op.add_column("trade_contracts", sa.Column("tlc_hash", sa.String(64), nullable=True), schema="app")
    op.add_column("trade_contracts", sa.Column("settlement_hold", sa.Boolean(), nullable=False, server_default="false"), schema="app")

    # 2. IGM tickets table
    op.create_table(
        "igm_tickets",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("ticket_id", sa.String(64), nullable=False),
        sa.Column("transaction_id", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("sub_category", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="OPEN"),
        sa.Column("escalation_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expected_response_time", sa.String(32), nullable=False, server_default="PT48H"),
        sa.Column("complainant_info", sa.JSON(), nullable=False),
        sa.Column("respondent_info", sa.JSON(), nullable=False),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("refund_amount_inr", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("settlement_paused", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sla_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("ticket_id", name="uq_igm_tickets_ticket_id"),
        schema="app",
    )
    op.create_index("ix_igm_tickets_transaction_id", "igm_tickets", ["transaction_id"], schema="app")
    op.create_index("ix_igm_tickets_status", "igm_tickets", ["status"], schema="app")

    # 3. Rating records table
    op.create_table(
        "rating_records",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("transaction_id", sa.String(128), nullable=False),
        sa.Column("rating_category", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="app",
    )
    op.create_index("ix_rating_records_transaction_id", "rating_records", ["transaction_id"], schema="app")
    op.create_index("ix_rating_records_target_id", "rating_records", ["target_id"], schema="app")

    # 4. TLC contracts table
    op.create_table(
        "tlc_records",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("contract_code", sa.String(160), nullable=False),
        sa.Column("transaction_id", sa.String(128), nullable=False),
        sa.Column("tlc_hash", sa.String(64), nullable=False),
        sa.Column("tlc_terms_json", sa.JSON(), nullable=False),
        sa.Column("signature", sa.String(256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("transaction_id", name="uq_tlc_records_transaction_id"),
        schema="app",
    )
    op.create_index("ix_tlc_records_tlc_hash", "tlc_records", ["tlc_hash"], schema="app")

    # 5. BAP tables
    op.create_table(
        "bap_search_requests",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("transaction_id", sa.String(128), nullable=False),
        sa.Column("message_id", sa.String(128), nullable=False),
        sa.Column("commodity", sa.String(64), nullable=True),
        sa.Column("grade", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("transaction_id", name="uq_bap_search_requests_transaction_id"),
        schema="app",
    )
    op.create_table(
        "bap_quotes",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("transaction_id", sa.String(128), nullable=False),
        sa.Column("message_id", sa.String(128), nullable=False),
        sa.Column("bpp_id", sa.String(128), nullable=False),
        sa.Column("bpp_uri", sa.String(512), nullable=False),
        sa.Column("lot_code", sa.String(64), nullable=False),
        sa.Column("commodity", sa.String(64), nullable=False),
        sa.Column("grade", sa.String(32), nullable=True),
        sa.Column("quantity_mt", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("price_inr", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("seller_score", sa.Float(), nullable=False, server_default="4.0"),
        sa.Column("raw_quote_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="app",
    )
    op.create_index("ix_bap_quotes_transaction_id", "bap_quotes", ["transaction_id"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_bap_quotes_transaction_id", table_name="bap_quotes", schema="app")
    op.drop_table("bap_quotes", schema="app")
    op.drop_table("bap_search_requests", schema="app")
    op.drop_index("ix_tlc_records_tlc_hash", table_name="tlc_records", schema="app")
    op.drop_table("tlc_records", schema="app")
    op.drop_index("ix_rating_records_target_id", table_name="rating_records", schema="app")
    op.drop_index("ix_rating_records_transaction_id", table_name="rating_records", schema="app")
    op.drop_table("rating_records", schema="app")
    op.drop_index("ix_igm_tickets_status", table_name="igm_tickets", schema="app")
    op.drop_index("ix_igm_tickets_transaction_id", table_name="igm_tickets", schema="app")
    op.drop_table("igm_tickets", schema="app")
    op.drop_column("trade_contracts", "settlement_hold", schema="app")
    op.drop_column("trade_contracts", "tlc_hash", schema="app")
    op.drop_column("trade_contracts", "role", schema="app")
    op.drop_column("trade_contracts", "bpp_id", schema="app")
    op.drop_column("trade_contracts", "bap_id", schema="app")
