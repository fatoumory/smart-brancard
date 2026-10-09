"""statut de mission ACCEPTE

Revision ID: eb7159c7b784
Revises: a7fe1aedb861
Create Date: 2026-10-09 09:38:41.986355

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'eb7159c7b784'
down_revision: Union[str, Sequence[str], None] = 'a7fe1aedb861'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ajoute ACCEPTE entre PROPOSE et EN_TRANSIT dans le type ENUM statut_mission."""
    # PostgreSQL n'accepte pas d'utiliser une nouvelle valeur d'ENUM dans la transaction
    # qui l'ajoute : on l'ajoute donc hors transaction (autocommit)
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE statut_mission ADD VALUE IF NOT EXISTS 'ACCEPTE' AFTER 'PROPOSE'")


def downgrade() -> None:
    """Retour arrière volontairement impossible.
    PostgreSQL ne sait pas retirer une valeur d'un ENUM : il faudrait recréer le type et réécrire
    les lignes ACCEPTE, y compris dans le journal d'audit, que le déclencheur rend immuable."""
    raise NotImplementedError("Le statut ACCEPTE ne peut pas être retiré (journal d'audit immuable)")
