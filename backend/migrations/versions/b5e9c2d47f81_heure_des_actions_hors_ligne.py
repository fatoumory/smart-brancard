"""heure des actions faites hors ligne (journal d'audit)

Revision ID: b5e9c2d47f81
Revises: a8d4f1b93c60
Create Date: 2026-11-12 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e9c2d47f81'
down_revision: Union[str, Sequence[str], None] = 'a8d4f1b93c60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ajoute l'heure donnée par le téléphone. Une nouvelle colonne ne modifie aucune ligne
    existante : le déclencheur qui rend le journal immuable n'est pas concerné."""
    op.add_column('historiques', sa.Column('horodatage_client', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('historiques', 'horodatage_client')
