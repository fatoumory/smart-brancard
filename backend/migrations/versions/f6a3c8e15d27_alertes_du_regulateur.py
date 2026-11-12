"""alertes du régulateur (appel d'un agent bloqué)

Revision ID: f6a3c8e15d27
Revises: e2b7d9c41a58
Create Date: 2026-11-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a3c8e15d27'
down_revision: Union[str, Sequence[str], None] = 'e2b7d9c41a58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crée la table alertes et son type raison_appel"""
    op.create_table(
        'alertes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mission_id', sa.Integer(), nullable=False),
        sa.Column('brancardier_id', sa.Integer(), nullable=False),
        sa.Column('raison', sa.Enum('ECHECS_SCAN', 'BRACELET_ILLISIBLE', 'AUTRE', name='raison_appel'),
                  nullable=False),
        sa.Column('date_creation', sa.DateTime(timezone=True), nullable=False),
        sa.Column('traitee', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('date_traitement', sa.DateTime(timezone=True), nullable=True),
        sa.Column('traitee_par_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['brancardier_id'], ['brancardiers.id']),
        sa.ForeignKeyConstraint(['mission_id'], ['missions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['traitee_par_id'], ['utilisateurs.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_alertes_id'), 'alertes', ['id'], unique=False)
    op.create_index(op.f('ix_alertes_mission_id'), 'alertes', ['mission_id'], unique=False)
    op.create_index(op.f('ix_alertes_traitee'), 'alertes', ['traitee'], unique=False)


def downgrade() -> None:
    """Supprime la table, puis son type"""
    op.drop_index(op.f('ix_alertes_traitee'), table_name='alertes')
    op.drop_index(op.f('ix_alertes_mission_id'), table_name='alertes')
    op.drop_index(op.f('ix_alertes_id'), table_name='alertes')
    op.drop_table('alertes')
    sa.Enum(name='raison_appel').drop(op.get_bind(), checkfirst=True)
