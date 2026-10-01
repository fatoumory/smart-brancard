"""ajout de la consigne de sécurité aux missions

Revision ID: a3c9e1f47b20
Revises: 62bfee3b99c0
Create Date: 2026-09-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c9e1f47b20'
down_revision: Union[str, Sequence[str], None] = '62bfee3b99c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('missions', sa.Column('consigne', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('missions', 'consigne')
