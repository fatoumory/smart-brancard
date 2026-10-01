# routes/graphe.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.enums import Role
from models.noeud_hopital import Arete, NoeudHopital
from models.utilisateur import Utilisateur
from schemas.graphe import AreteBlocage, AreteOut
from services.auth_service import require_role

# Préfixe commun à toutes les routes de ce fichier: /aretes/...
router = APIRouter(prefix="/aretes", tags=["Graphe de l'hôpital"])


def vers_arete_out(arete: Arete, noms: dict[int, str]) -> AreteOut:
    """Ajoute le nom des deux nœuds à l'arête (la table aretes ne contient que leurs id)"""
    return AreteOut(
        id=arete.id,
        noeud_a_id=arete.noeud_a_id,
        noeud_a_nom=noms[arete.noeud_a_id],
        noeud_b_id=arete.noeud_b_id,
        noeud_b_nom=noms[arete.noeud_b_id],
        poids=arete.poids,
        est_bloque=arete.est_bloque,
    )


def noms_par_id(db: Session) -> dict[int, str]:
    """Dictionnaire {id du nœud: nom de la salle}"""
    return dict(db.query(NoeudHopital.id, NoeudHopital.nom_salle).all())


#  Liste des arêtes (régulateur uniquement)
# Exemple : GET /aretes?est_bloque=true pour voir les pannes en cours
@router.get("", response_model=list[AreteOut])
def lister_aretes(
    est_bloque: bool | None = None,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_role([Role.REGULATEUR]))
):
    requete = db.query(Arete)
    if est_bloque is not None:
        requete = requete.filter(Arete.est_bloque.is_(est_bloque))
    noms = noms_par_id(db)
    return [vers_arete_out(a, noms) for a in requete.order_by(Arete.id).all()]


#  Bloquer ou débloquer une arête (régulateur uniquement)
# Ascenseur en panne, couloir fermé : Dijkstra ignore l'arête dès le calcul suivant
@router.patch("/{arete_id}", response_model=AreteOut)
def bloquer_arete(
    arete_id: int,
    donnees: AreteBlocage,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_role([Role.REGULATEUR]))
):
    arete = db.get(Arete, arete_id)
    if arete is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arête introuvable"
        )

    arete.est_bloque = donnees.est_bloque
    db.commit()
    db.refresh(arete)
    return vers_arete_out(arete, noms_par_id(db))
