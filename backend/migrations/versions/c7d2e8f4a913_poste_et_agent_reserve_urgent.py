"""poste d'attente des brancardiers et agent réservé aux URGENT

Revision ID: c7d2e8f4a913
Revises: b5e9c2d47f81
Create Date: 2026-11-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d2e8f4a913'
down_revision: Union[str, Sequence[str], None] = 'b5e9c2d47f81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Deux réglages par brancardier, choisis par le régulateur (rapport Sprint 5, § 4.3).
    Les agents existants n'ont pas de poste et ne sont pas réservés : rien ne change pour eux."""
    op.add_column('brancardiers', sa.Column('poste_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_brancardiers_poste', 'brancardiers', 'noeuds_hopital',
                          ['poste_id'], ['id'], ondelete='SET NULL')
    op.add_column('brancardiers', sa.Column('reserve_urgent', sa.Boolean(), nullable=False,
                                            server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('brancardiers', 'reserve_urgent')
    op.drop_constraint('fk_brancardiers_poste', 'brancardiers', type_='foreignkey')
    op.drop_column('brancardiers', 'poste_id')
