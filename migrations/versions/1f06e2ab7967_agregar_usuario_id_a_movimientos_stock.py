from alembic import op
import sqlalchemy as sa

revision = "1f06e2ab7967"
down_revision = "02f1403380bf"


def upgrade():
    op.add_column(
        "movimientos_stock",
        sa.Column("usuario_id", sa.Integer(), nullable=True)
    )

def downgrade():
    op.drop_column("movimientos_stock", "usuario_id")
