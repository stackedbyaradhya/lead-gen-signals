"""Initial outcome ranking schema."""

from alembic import op
import sqlalchemy as sa


revision = "20261012_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(255), nullable=False),
        sa.Column("employees", sa.Integer(), nullable=False),
        sa.Column("message_variant", sa.String(255), nullable=False),
        sa.Column("baseline_score", sa.Float(), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.Column("import_batch_id", sa.Integer(), sa.ForeignKey("import_batches.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_leads_external_id", "leads", ["external_id"])
    op.create_index("ix_leads_industry", "leads", ["industry"])
    op.create_index("ix_leads_employees", "leads", ["employees"])
    op.create_index("ix_leads_message_variant", "leads", ["message_variant"])
    op.create_index("ix_leads_outcome", "leads", ["outcome"])
    op.create_index("ix_leads_industry_employees", "leads", ["industry", "employees"])
    op.create_table(
        "outcome_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_outcome_events_lead_id", "outcome_events", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_outcome_events_lead_id", table_name="outcome_events")
    op.drop_table("outcome_events")
    op.drop_index("ix_leads_industry_employees", table_name="leads")
    op.drop_index("ix_leads_outcome", table_name="leads")
    op.drop_index("ix_leads_message_variant", table_name="leads")
    op.drop_index("ix_leads_employees", table_name="leads")
    op.drop_index("ix_leads_industry", table_name="leads")
    op.drop_index("ix_leads_external_id", table_name="leads")
    op.drop_table("leads")
    op.drop_table("import_batches")
