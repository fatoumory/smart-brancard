# seed_graphe.py
# Charge le plan de l'hôpital (data/graphe_hopital.json) dans la base
# Prérequis : les tables existent (alembic upgrade head)
# Utilisation : python seed_graphe.py

import models  # enregistre tous les modèles
from database import SessionLocal
from services.graphe_service import calculer_itineraire, charger_graphe_json, noms_des_noeuds


def main():
    db = SessionLocal()
    try:
        nombre = charger_graphe_json(db)
        if nombre:
            print(f"{nombre} nœuds chargés")
        else:
            print("Le graphe est déjà en base : rien à faire")

        # Vérification rapide : Urgences (1) -> Réanimation (13), attendu 5.0 min par l'ascenseur B
        chemin, duree = calculer_itineraire(db, 1, 13)
        print(f"Urgences -> Réanimation : {duree} min")
        print("  " + " -> ".join(noms_des_noeuds(db, chemin)))
    finally:
        db.close()


if __name__ == "__main__":
    main()


#Le script charge le graphe, puis vérifie tout de suite le trajet de référence. Si le graphe est déjà en base, il ne fait rien.