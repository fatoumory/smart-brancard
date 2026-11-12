"""méthode de vérification BALISE (arrivée détectée par le badge)

Revision ID: e2b7d9c41a58
Revises: c4e8a1f2b6d3
Create Date: 2026-11-12 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e2b7d9c41a58'
down_revision: Union[str, Sequence[str], None] = 'c4e8a1f2b6d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Ajoute BALISE au type ENUM methode_verification."""
    # PostgreSQL n'accepte pas d'utiliser une nouvelle valeur d'ENUM dans la transaction
    # qui l'ajoute : on l'ajoute donc hors transaction (autocommit)
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE methode_verification ADD VALUE IF NOT EXISTS 'BALISE'")


def downgrade() -> None:
    """Retour arrière volontairement impossible.
    PostgreSQL ne sait pas retirer une valeur d'un ENUM : il faudrait recréer le type et réécrire
    les lignes BALISE du journal d'audit, que le déclencheur rend immuable."""
    raise NotImplementedError("La méthode BALISE ne peut pas être retirée (journal d'audit immuable)")
