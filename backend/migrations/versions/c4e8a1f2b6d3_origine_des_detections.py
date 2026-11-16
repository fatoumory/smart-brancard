"""origine des détections (badge, scan, déclaration)

Revision ID: c4e8a1f2b6d3
Revises: d90d00dbc187
Create Date: 2026-11-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8a1f2b6d3'
down_revision: Union[str, Sequence[str], None] = 'd90d00dbc187'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

origine_detection = sa.Enum('BADGE', 'SCAN', 'DECLARATION', name='origine_detection')


def upgrade() -> None:
    """Ajoute l'origine de chaque détection.
    Les détections déjà enregistrées ne disent pas d'où elles viennent : elles comptent comme
    des déclarations, qui ne prouvent pas la présence (le choix le plus prudent)."""
    origine_detection.create(op.get_bind(), checkfirst=True)
    op.add_column('detections', sa.Column('origine', origine_detection, nullable=False,
                                          server_default='DECLARATION'))


def downgrade() -> None:
    """Retire la colonne puis le type"""
    op.drop_column('detections', 'origine')
    origine_detection.drop(op.get_bind(), checkfirst=True)
