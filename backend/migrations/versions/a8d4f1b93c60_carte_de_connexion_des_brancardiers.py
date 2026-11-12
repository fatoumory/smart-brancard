"""carte de connexion des brancardiers (empreinte du code QR)

Revision ID: a8d4f1b93c60
Revises: f6a3c8e15d27
Create Date: 2026-11-12 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8d4f1b93c60'
down_revision: Union[str, Sequence[str], None] = 'f6a3c8e15d27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ajoute l'empreinte de la carte de connexion, unique (une carte = un seul compte)"""
    op.add_column('utilisateurs', sa.Column('carte_hash', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_utilisateurs_carte_hash'), 'utilisateurs', ['carte_hash'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_utilisateurs_carte_hash'), table_name='utilisateurs')
    op.drop_column('utilisateurs', 'carte_hash')
