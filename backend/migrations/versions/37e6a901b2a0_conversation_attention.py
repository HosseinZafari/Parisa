"""اطلاعات عمومی فروشنده و صف پایدار رسیدگی به گفتگوها."""

from alembic import op
import sqlalchemy as sa

revision = "37e6a901b2a0"
down_revision = "8c6d8d6608cc"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sellers", sa.Column("public_profile", sa.JSON(), nullable=False, server_default="{}"))
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("attention_status", sa.String(20), nullable=False, server_default="none"))
        batch.add_column(sa.Column("attention_priority", sa.String(20), nullable=False, server_default="normal"))
        batch.add_column(sa.Column("attention_version", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("handover_reason", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("attention_resolved_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("attention_resolved_by", sa.String(100), nullable=True))
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("conversation_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("priority", sa.String(20), nullable=False, server_default="normal"))
        batch.create_foreign_key("fk_notifications_conversation", "conversations", ["conversation_id"], ["id"])
    op.execute(
        "UPDATE conversations SET attention_status='open', attention_version=1, handover_reason='درخواست پاسخ فروشنده' WHERE handover=1"
    )


def downgrade():
    with op.batch_alter_table("notifications") as batch:
        batch.drop_constraint("fk_notifications_conversation", type_="foreignkey")
        batch.drop_column("conversation_id")
        batch.drop_column("priority")
    with op.batch_alter_table("conversations") as batch:
        for name in [
            "attention_resolved_by",
            "attention_resolved_at",
            "handover_reason",
            "attention_version",
            "attention_priority",
            "attention_status",
        ]:
            batch.drop_column(name)
    with op.batch_alter_table("sellers") as batch:
        batch.drop_column("public_profile")
