# loadtest/hypotheses.py
# Hypothèses de charge communes aux tests Locust et à l'analyse de la file d'attente (Sprint 5).
#
# Elles sont tirées de données officielles sénégalaises :
#   Ministère de la Santé et de l'Action sociale (MSAS), Direction de la Planification, de la
#   Recherche et des Statistiques, « Annuaire des statistiques sanitaires et sociales »
#   - édition 2021, tableau 80 : malades hospitalisés par établissement ;
#   - édition 2020, tableau 22 : lits installés et taux d'occupation.
#
# Hôpital de référence : Hôpital Général Idrissa Pouye (HOGIP, Grand Yoff, Dakar), hôpital
# général dont les services correspondent à ceux du graphe du prototype (urgences, radiologie,
# bloc, réanimation, cardiologie, laboratoire...).
#
# Seul le nombre de transports par séjour est une hypothèse : il est testé de 2 à 4
# (analyse de sensibilité).

# --- Données de l'annuaire -------------------------------------------------------------------
HOSPITALISATIONS_PAR_AN = 12_615   # HOGIP, 2021 (annuaire 2021, tableau 80)
LITS_INSTALLES = 235               # HOGIP, 2020 (annuaire 2020, tableau 22)
TAUX_OCCUPATION = 0.55             # HOGIP, 2020 (annuaire 2020, tableau 22)

# --- Hypothèses ------------------------------------------------------------------------------
# Transports par séjour : arrivée dans le service, examens (radiologie, scanner...), bloc, sortie
TRANSPORTS_PAR_SEJOUR = {"bas": 2, "base": 3, "haut": 4}

# Répartition dans la journée : 75 % des transports entre 8 h et 18 h (10 h), le reste la nuit (14 h)
PART_JOURNEE = 0.75
HEURES_JOURNEE = 10
HEURES_NUIT = 14
# Pic de fin de matinée (examens et blocs programmés) : 1,5 fois la moyenne de journée
FACTEUR_PIC = 1.5

# Part de chaque niveau d'urgence (la plupart des transports sont programmés)
PART_URGENCES = {"URGENT": 0.05, "HAUTE": 0.15, "MOYENNE": 0.40, "BASSE": 0.40}

# Délais garantis de prise en charge, en minutes (identiques au backend : DELAI_GARANTI_MIN)
DELAIS_GARANTIS_MIN = {"URGENT": 3, "HAUTE": 8, "MOYENNE": 15, "BASSE": 30}

# Durée d'une mission hors trajet (minutes) : installation du patient au départ, après le scan du
# bracelet (la prise en charge), et remise à l'arrivée
DUREE_INSTALLATION_MIN = 3
DUREE_REMISE_MIN = 2

# Comportement des agents
PART_ACCEPTATIONS = 0.90           # 10 % de refus
REPONSE_AGENT_S = (5, 20)          # délai de réponse à une proposition, en secondes


def demandes_par_heure(periode: str = "journee", transports_par_sejour: int = 3) -> float:
    """Nombre moyen de demandes de transport par heure pour une période de la journée.
    periode : "journee" (8 h - 18 h), "pic" (fin de matinée) ou "nuit" (18 h - 8 h)"""
    par_jour = HOSPITALISATIONS_PAR_AN / 365 * transports_par_sejour
    journee = par_jour * PART_JOURNEE / HEURES_JOURNEE
    if periode == "journee":
        return journee
    if periode == "pic":
        return journee * FACTEUR_PIC
    if periode == "nuit":
        return par_jour * (1 - PART_JOURNEE) / HEURES_NUIT
    raise ValueError(f"Période inconnue : {periode}")


if __name__ == "__main__":
    # Affiche le tableau des débits utilisé dans le rapport
    print(f"Admissions par jour : {HOSPITALISATIONS_PAR_AN / 365:.1f}")
    for nom, k in TRANSPORTS_PAR_SEJOUR.items():
        debits = ", ".join(f"{p} {demandes_par_heure(p, k):.1f}/h" for p in ("journee", "pic", "nuit"))
        print(f"{k} transports par séjour ({nom}) : {debits}")
