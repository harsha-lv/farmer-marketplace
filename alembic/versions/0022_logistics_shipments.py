"""Alembic migration 0022: Logistics LSP shipments table.

Creates shipments table in schema ``app`` for tracking ONDC Logistics Service
Provider (LSP) bookings, lifecycle states, live GPS coordinates, SLA windows,
and IGM links.

Revision ID: 0022_logistics_shipments
Revises: 0021_lgd_reference_data
Create Date: 2026-09-25
"""

import sqlalchemy as sa
from alembic import op

revision = "0022_logistics_shipments"
down_revision = "0021_lgd_reference_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shipments",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("shipment_id", sa.String(64), nullable=False),
        sa.Column("transaction_id", sa.String(128), nullable=False),
        sa.Column("order_id", sa.String(128), nullable=True),
        sa.Column("trade_contract_id", sa.BigInteger, nullable=True),
        sa.Column("contract_code", sa.String(160), nullable=True),
        sa.Column("lsp_id", sa.String(128), nullable=False),
        sa.Column("lsp_name", sa.String(128), nullable=True),
        sa.Column("lsp_uri", sa.String(512), nullable=True),
        sa.Column("quote_id", sa.String(128), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="network"),
        sa.Column("state", sa.String(64), nullable=False, server_default="CREATED"),
        sa.Column("pickup_gps", sa.String(64), nullable=False),
        sa.Column("drop_gps", sa.String(64), nullable=False),
        sa.Column("pickup_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pickup_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_pickup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("eta_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_gps", sa.String(64), nullable=True),
        sa.Column("last_gps_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tracking_url", sa.String(512), nullable=True),
        sa.Column("vehicle_type", sa.String(64), nullable=True),
        sa.Column("vehicle_number", sa.String(64), nullable=True),
        sa.Column("cold_chain", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("freight_charge_inr", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("sla_status", sa.String(32), nullable=False, server_default="ON_TIME"),
        sa.Column("igm_ticket_id", sa.String(64), nullable=True),
        sa.Column("raw_details", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("shipment_id", name="uq_shipments_shipment_id"),
        schema="app",
    )
    op.create_index("ix_shipments_transaction_id", "shipments", ["transaction_id"], schema="app")
    op.create_index("ix_shipments_lsp_id", "shipments", ["lsp_id"], schema="app")
    op.create_index("ix_shipments_state", "shipments", ["state"], schema="app")
    op.create_index("ix_shipments_sla_status", "shipments", ["sla_status"], schema="app")
    op.create_index("ix_shipments_eta_delivery_at", "shipments", ["eta_delivery_at"], schema="app")


def downgrade() -> None:
    op.drop_index("ix_shipments_eta_delivery_at", table_name="shipments", schema="app")
    op.drop_index("ix_shipments_sla_status", table_name="shipments", schema="app")
    op.drop_index("ix_shipments_state", table_name="shipments", schema="app")
    op.drop_index("ix_shipments_lsp_id", table_name="shipments", schema="app")
    op.drop_index("ix_shipments_transaction_id", table_name="shipments", schema="app")
    op.drop_table("shipments", schema="app")
