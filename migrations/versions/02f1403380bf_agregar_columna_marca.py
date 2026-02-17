from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "02f1403380bf"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ✅ SOLO agregar columna marca a productos
    op.add_column(
        "productos",
        sa.Column("marca", sa.String(length=100), nullable=True)
    )


def downgrade():
    # ✅ Solo eliminar columna marca si se revierte
    op.drop_column("productos", "marca")
