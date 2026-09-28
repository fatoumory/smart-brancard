"""historique immuable

Revision ID: b1a82a133f64
Revises: bf7a49c18961
Create Date: 2026-09-28 20:26:24.156392

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b1a82a133f64'
down_revision: Union[str, Sequence[str], None] = 'bf7a49c18961'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Fonction PostgreSQL qui refuse toute modification : elle lève une erreur
    op.execute("""
        CREATE FUNCTION historiques_immuable() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Le journal d''audit est immuable : modification et suppression interdites';
        END;
        $$ LANGUAGE plpgsql;
    """)
    # Déclencheur : la fonction s'exécute avant chaque UPDATE ou DELETE sur la table historiques
    op.execute("""
        CREATE TRIGGER historiques_immuable
        BEFORE UPDATE OR DELETE ON historiques
        FOR EACH ROW EXECUTE FUNCTION historiques_immuable();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS historiques_immuable ON historiques;")
    op.execute("DROP FUNCTION IF EXISTS historiques_immuable();")
