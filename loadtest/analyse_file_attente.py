# loadtest/analyse_file_attente.py
# Analyse stochastique de la file d'attente des transports (Sprint 5).
#
# Question : combien de brancardiers faut-il, selon la période, pour respecter les délais garantis
# de prise en charge (URGENT 3 min, HAUTE 8, MOYENNE 15, BASSE 30) ?
#
# Deux approches, avec les hypothèses de hypotheses.py (données de l'HOGIP) :
#
# 1. Modèle analytique : file M/M/c à priorités non préemptives (formule de Cobham). Les demandes
#    arrivent selon un processus de Poisson, c agents servent la file dans l'ordre des urgences.
#    Il donne la charge des agents et l'attente moyenne, mais pas les trajets réels.
#
# 2. Simulation à événements discrets, fidèle aux règles de l'application :
#    - plan de l'hôpital (backend/data/graphe_hopital.json) et plus courts chemins (Dijkstra) ;
#    - file servie par urgence puis ancienneté ; agent choisi par le score du backend
#      (trajet + 0,5 min par mission déjà faite, trajet seul en URGENT) ;
#    - réponse en 5 à 20 s, 10 % de refus (l'agent est retenu 15 min) ;
#    - la prise en charge est le scan du bracelet, à l'arrivée de l'agent près du patient ;
#    - installation 3 min, transport, remise 2 min ; l'agent reste à l'arrivée.
#
# 3. Agents postés : des agents qui reviennent attendre à un poste fixe (Urgences, ou un point central
#    par étage), éventuellement réservés aux URGENT. Ce n'est pas dans l'application actuelle :
#    c'est une règle d'organisation testée pour tenir le délai URGENT de 3 min.
#
# Utilisation : python analyse_file_attente.py            (tableaux + resultats/analyse_*.csv)
#               python analyse_file_attente.py --rapide   (simulation plus courte, pour tester)

import argparse
import csv
import heapq
import json
import math
import random
import statistics
from pathlib import Path

import hypotheses as H

RACINE = Path(__file__).resolve().parent
GRAPHE = RACINE.parent / "backend" / "data" / "graphe_hopital.json"
DOSSIER_RESULTATS = RACINE / "resultats"

# Règles du backend (services/assignation_service.py)
K_EQUITE_MIN = {"URGENT": 0.0, "HAUTE": 0.5, "MOYENNE": 0.5, "BASSE": 0.5}
RETENUE_URGENCE_MIN = 15
URGENCES = list(H.PART_URGENCES)          # ordre de priorité : URGENT d'abord
RANG = {u: i for i, u in enumerate(URGENCES)}

# Critère de dimensionnement : 95 % des missions HAUTE, MOYENNE et BASSE prises en charge dans le délai
# garanti. URGENT est suivi à part : son délai (3 min) est plus court que bien des trajets du plan
# (jusqu'à 5,5 min d'un service à l'autre), il dépend surtout de la position des agents, pas de leur nombre
OBJECTIF = {"HAUTE": 0.95, "MOYENNE": 0.95, "BASSE": 0.95}


# --- Plan de l'hôpital -----------------------------------------------------------------------
def charger_plan():
    donnees = json.loads(GRAPHE.read_text(encoding="utf-8"))
    noeuds = [n for n in donnees["noeuds"] if "id" in n]
    voisins = {n["id"]: [] for n in noeuds}
    for a in donnees["aretes"]:
        if "poids" in a and not a.get("est_bloque"):
            voisins[a["noeud_a_id"]].append((a["noeud_b_id"], a["poids"]))
            voisins[a["noeud_b_id"]].append((a["noeud_a_id"], a["poids"]))
    services = [n["id"] for n in noeuds if n["type_noeud"] == "SERVICE"]
    return services, {s: dijkstra(voisins, s) for s in voisins}


def dijkstra(voisins, depart):
    distances, tas = {depart: 0.0}, [(0.0, depart)]
    while tas:
        d, n = heapq.heappop(tas)
        if d > distances[n]:
            continue
        for v, poids in voisins[n]:
            if d + poids < distances.get(v, math.inf):
                distances[v] = d + poids
                heapq.heappush(tas, (d + poids, v))
    return distances


SERVICES, DISTANCES = charger_plan()
PAIRES = [(a, b) for a in SERVICES for b in SERVICES if a != b]
TRAJET_MOYEN_MIN = statistics.mean(DISTANCES[a][b] for a, b in PAIRES)
REPONSE_MOYENNE_MIN = sum(H.REPONSE_AGENT_S) / 2 / 60


# --- 1. Modèle analytique --------------------------------------------------------------------
def erlang_c(c: int, a: float) -> float:
    """Probabilité d'attendre dans une file M/M/c (a = charge offerte = lambda × durée moyenne)"""
    if a >= c:
        return 1.0
    terme, somme = 1.0, 1.0
    for k in range(1, c):
        terme *= a / k
        somme += terme
    terme *= a / c
    dernier = terme * c / (c - a)
    return dernier / (somme + dernier)


def modele_analytique(debit_h: float, c: int) -> dict:
    """Charge des agents et attente moyenne dans la file par urgence (minutes), formule de Cobham.
    Durée de service : trajet moyen entre deux services pour rejoindre le patient (valeur prudente :
    l'agent choisi est en fait le plus proche) + installation + transport + remise."""
    duree = REPONSE_MOYENNE_MIN + TRAJET_MOYEN_MIN + H.DUREE_INSTALLATION_MIN + TRAJET_MOYEN_MIN \
        + H.DUREE_REMISE_MIN
    lam = debit_h / 60                     # demandes par minute
    a = lam * duree
    rho = a / c
    if rho >= 1:
        return {"duree_service_min": duree, "occupation": rho, "attente": {u: math.inf for u in URGENCES}}
    w0 = erlang_c(c, a) * duree / c        # attente résiduelle moyenne avant qu'un agent se libère
    attente, sigma = {}, 0.0
    for u in URGENCES:
        precedent = sigma
        sigma += lam * H.PART_URGENCES[u] * duree / c
        attente[u] = w0 / ((1 - precedent) * (1 - sigma))
    return {"duree_service_min": duree, "occupation": rho, "attente": attente}


# --- 2. Simulation à événements discrets -----------------------------------------------------
class Agent:
    def __init__(self, ident, lieu, poste=None):
        self.id, self.lieu, self.libre, self.missions = ident, lieu, True, 0
        self.poste = poste      # lieu où l'agent revient attendre entre deux missions (None : il reste sur place)
        self.jeton = 0          # invalide un retour au poste interrompu par une nouvelle mission


# Lieux du plan utilisés pour les postes et la variante « URGENT concentrées »
URGENCES_NOEUD, BLOC, REANIMATION = 1, 11, 13
HALL_RDC, PALIER_ETAGE = 6, 16
# Variante : origine des URGENT (hypothèse, aucune donnée publiée) : surtout des Urgences
SOURCES_URGENT_CONCENTREES = {URGENCES_NOEUD: 0.6, REANIMATION: 0.2, BLOC: 0.2}


def simuler(debit_h: float, c: int, heures: float, graine: int, prechauffe_h: float = 5,
            postes: tuple = (), reserve: bool = False, sources_urgent: dict | None = None) -> dict:
    """Simule `heures` heures à débit constant. Renvoie, par urgence, la liste des attentes avant
    prise en charge (minutes) des missions créées après le préchauffage, et l'occupation des agents.
    postes : lieux d'attente des premiers agents (ils y reviennent après chaque mission) ;
    reserve : ces agents postés ne prennent que des missions URGENT ;
    sources_urgent : lieux de départ des URGENT et leur poids (sinon un service au hasard)."""
    alea = random.Random(graine)
    agents = [Agent(i, postes[i], postes[i]) if i < len(postes) else Agent(i, alea.choice(SERVICES))
              for i in range(c)]
    file = []                               # missions en attente : (rang urgence, création, n°)
    missions = {}                           # n° -> (urgence, création, source, destination)
    evenements, compteur = [], 0
    attentes = {u: [] for u in URGENCES}
    temps_occupe = 0.0
    fin = heures * 60

    def planifier(t, *quoi):
        nonlocal compteur
        compteur += 1
        heapq.heappush(evenements, (t, compteur, quoi))

    def repartir(t):
        """Comme traiter_file_attente : chaque mission, dans l'ordre, à l'agent libre de plus petit score"""
        for cle in sorted(file):
            if not any(ag.libre for ag in agents):
                return
            urgence, _, source, _ = missions[cle[2]]
            libres = [ag for ag in agents if ag.libre and not (reserve and ag.poste and urgence != "URGENT")]
            if not libres:
                continue
            k = K_EQUITE_MIN[urgence]
            agent = min(libres, key=lambda ag: (DISTANCES[source][ag.lieu] + k * ag.missions, ag.missions, ag.id))
            file.remove(cle)
            agent.libre = False
            agent.jeton += 1
            planifier(t + alea.uniform(*H.REPONSE_AGENT_S) / 60, "reponse", agent, cle)

    def nouvelle_demande(t):
        n = len(missions)
        urgence = alea.choices(URGENCES, weights=list(H.PART_URGENCES.values()))[0]
        if urgence == "URGENT" and sources_urgent:
            source = alea.choices(list(sources_urgent), weights=list(sources_urgent.values()))[0]
            destination = alea.choice([s for s in SERVICES if s != source])
        else:
            source, destination = alea.choice(PAIRES)
        missions[n] = (urgence, t, source, destination)
        file.append((RANG[urgence], t, n))
        planifier(t + alea.expovariate(debit_h / 60), "demande")

    planifier(alea.expovariate(debit_h / 60), "demande")
    while evenements:
        t, _, (quoi, *args) = heapq.heappop(evenements)
        if t > fin:
            break
        if quoi == "demande":
            nouvelle_demande(t)
        elif quoi == "reponse":
            agent, cle = args
            urgence, cree, source, destination = missions[cle[2]]
            if alea.random() >= H.PART_ACCEPTATIONS:
                # Refus « urgence prioritaire » : la mission repart dans la file, l'agent est retenu 15 min
                file.append(cle)
                planifier(t + RETENUE_URGENCE_MIN, "retour", agent, False)
                if cree >= prechauffe_h * 60:
                    temps_occupe += RETENUE_URGENCE_MIN
            else:
                prise = t + DISTANCES[agent.lieu][source]
                liberation = prise + H.DUREE_INSTALLATION_MIN + DISTANCES[source][destination] + H.DUREE_REMISE_MIN
                if cree >= prechauffe_h * 60:
                    attentes[urgence].append(prise - cree)
                    temps_occupe += liberation - t
                agent.lieu = destination
                planifier(liberation, "retour", agent, True)
        elif quoi == "retour":
            agent, mission_faite = args
            agent.libre = True
            if mission_faite:
                agent.missions += 1     # compteur d'équité, comme à la clôture dans le backend
            if agent.poste and agent.lieu != agent.poste:
                # Il retourne à son poste ; il reste sollicitable en chemin (compté à son dernier lieu)
                planifier(t + DISTANCES[agent.lieu][agent.poste], "au_poste", agent, agent.jeton)
        elif quoi == "au_poste":
            agent, jeton = args
            if agent.libre and agent.jeton == jeton:
                agent.lieu = agent.poste
        repartir(t)

    duree_mesure = (heures - prechauffe_h) * 60
    return {"attentes": attentes, "occupation": temps_occupe / (c * duree_mesure),
            "en_attente_a_la_fin": len(file)}


def resumer(attentes: dict) -> dict:
    resume = {}
    for u, valeurs in attentes.items():
        if not valeurs:
            resume[u] = {"n": 0, "moyenne": None, "p90": None, "dans_le_delai": None}
            continue
        valeurs = sorted(valeurs)
        resume[u] = {
            "n": len(valeurs),
            "moyenne": statistics.mean(valeurs),
            "p90": valeurs[int(0.9 * (len(valeurs) - 1))],
            "dans_le_delai": sum(v <= H.DELAIS_GARANTIS_MIN[u] for v in valeurs) / len(valeurs),
        }
    return resume


def respecte_objectif(resume: dict) -> bool:
    return all(resume[u]["dans_le_delai"] is not None and resume[u]["dans_le_delai"] >= OBJECTIF[u]
               for u in OBJECTIF)


def pct(x) -> str:
    return "–" if x is None or x == "" else f"{100 * x:.0f} %"


def minutes(x) -> str:
    return "–" if x is None or x == "" else f"{x:.1f}"


# --- Programme principal ---------------------------------------------------------------------
def comparer_locust(chemin_synthese: Path, repetitions: int = 200) -> None:
    """Compare un test Locust à la simulation des mêmes conditions. Un test Locust est une seule journée
    (quelques dizaines de missions) : on simule `repetitions` journées identiques, au départ sans file
    d'attente, et on regarde si le résultat de Locust tombe dans la fourchette attendue (5e-95e centile)."""
    locust = json.loads(Path(chemin_synthese).read_text(encoding="utf-8"))
    debit = H.demandes_par_heure(locust["periode"], locust["transports_par_sejour"])
    heures = locust["duree_hopital_h"] if "duree_hopital_h" in locust else 10
    par_journee = {u: {"moyenne": [], "dans_le_delai": []} for u in URGENCES}
    for graine in range(repetitions):
        resume = resumer(simuler(debit, locust["agents"], heures, graine=graine, prechauffe_h=0)["attentes"])
        for u in URGENCES:
            if resume[u]["n"]:
                par_journee[u]["moyenne"].append(resume[u]["moyenne"])
                par_journee[u]["dans_le_delai"].append(resume[u]["dans_le_delai"])

    def fourchette(valeurs, format_):
        valeurs = sorted(valeurs)
        bas, haut = valeurs[int(0.05 * (len(valeurs) - 1))], valeurs[int(0.95 * (len(valeurs) - 1))]
        return f"{format_(statistics.median(valeurs))} ({format_(bas)} à {format_(haut)})"

    lignes = [
        "# Comparaison : test de charge Locust et simulation",
        "",
        f"Conditions : {locust['agents']} agents, période {locust['periode']}, "
        f"{locust['transports_par_sejour']} transports par séjour ({debit:.1f} demandes/h), {heures:g} h d'hôpital, "
        f"temps accéléré ×{locust['acceleration']:g} pour Locust.",
        f"Simulation : {repetitions} journées identiques ; médiane et fourchette 5e-95e centile.",
        "",
        "| Urgence | Missions Locust | Attente moyenne Locust (min) | Attente moyenne simulée (min) "
        "| Dans le délai, Locust | Dans le délai, simulation |",
        "|---|---|---|---|---|---|",
    ]
    for u in URGENCES:
        l = locust["par_urgence"][u]
        lignes.append(f"| {u} | {l['prises_en_charge']} | {minutes(l['attente_moyenne_min'])} "
                      f"| {fourchette(par_journee[u]['moyenne'], minutes)} | {pct(l['part_dans_le_delai'])} "
                      f"| {fourchette(par_journee[u]['dans_le_delai'], pct)} |")
    texte = "\n".join(lignes) + "\n"
    (RACINE / "comparaison_locust.md").write_text(texte, encoding="utf-8")
    print(texte)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rapide", action="store_true", help="simulation courte (essai)")
    parser.add_argument("--agents-max", type=int, default=12)
    parser.add_argument("--comparer", metavar="SYNTHESE_JSON",
                        help="compare un test Locust (resultats/*_synthese.json) à la simulation")
    args = parser.parse_args()
    if args.comparer:
        comparer_locust(Path(args.comparer))
        return
    heures = 300 if args.rapide else 2000

    print(f"Plan : {len(SERVICES)} services, trajet moyen entre deux services {TRAJET_MOYEN_MIN:.2f} min")
    print(f"Simulation : {heures} h par configuration (5 h de préchauffage)\n")

    lignes, besoins, detail_base = [], [], []
    for k in H.TRANSPORTS_PAR_SEJOUR.values():
        for periode in ("journee", "pic", "nuit"):
            debit = H.demandes_par_heure(periode, k)
            besoin = minimum = None
            for c in range(1, args.agents_max + 1):
                analytique = modele_analytique(debit, c)
                if analytique["occupation"] >= 1:
                    continue                # file instable : elle grandit sans fin
                minimum = minimum or c
                sim = simuler(debit, c, heures, graine=1000 * k + c)
                resume = resumer(sim["attentes"])
                ok = respecte_objectif(resume)
                if ok and besoin is None:
                    besoin = {"agents": c, "occupation": sim["occupation"], "resume": resume}
                if k == 3 and periode == "journee":
                    detail_base.append((c, analytique, sim, resume))
                for u in URGENCES:
                    lignes.append({
                        "transports_par_sejour": k, "periode": periode, "demandes_par_heure": round(debit, 2),
                        "agents": c, "urgence": u,
                        "occupation_analytique": round(analytique["occupation"], 3),
                        "occupation_simulee": round(sim["occupation"], 3),
                        "attente_file_analytique_min": round(analytique["attente"][u], 2),
                        "missions_simulees": resume[u]["n"],
                        "attente_moyenne_min": round(resume[u]["moyenne"], 2) if resume[u]["n"] else "",
                        "attente_p90_min": round(resume[u]["p90"], 2) if resume[u]["n"] else "",
                        "part_dans_le_delai": round(resume[u]["dans_le_delai"], 3) if resume[u]["n"] else "",
                        "objectif_atteint": ok,
                    })
            besoins.append((k, periode, debit, minimum, besoin))

    DOSSIER_RESULTATS.mkdir(exist_ok=True)
    with open(DOSSIER_RESULTATS / "analyse_file_attente.csv", "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=list(lignes[0]))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)

    # Tableaux pour le rapport (Markdown), versionnés avec le script
    noms = {"journee": "journée (8 h-18 h)", "pic": "pic de fin de matinée", "nuit": "nuit (18 h-8 h)"}
    t1 = ["| Transports par séjour | Période | Demandes/h | Agents minimum (file stable) | Agents nécessaires "
          "| Occupation | URGENT pris en charge en 3 min |", "|---|---|---|---|---|---|---|"]
    for k, periode, debit, minimum, besoin in besoins:
        if besoin:
            t1.append(f"| {k} | {noms[periode]} | {debit:.1f} | {minimum} | **{besoin['agents']}** "
                      f"| {pct(besoin['occupation'])} | {pct(besoin['resume']['URGENT']['dans_le_delai'])} |")
        else:
            t1.append(f"| {k} | {noms[periode]} | {debit:.1f} | {minimum} | > {args.agents_max} | – | – |")

    t2 = ["| Agents | Occupation (formule / simulation) | " + " | ".join(
        f"{u} : attente moy. (min) / dans {H.DELAIS_GARANTIS_MIN[u]} min" for u in URGENCES) + " |",
          "|---|---|" + "---|" * len(URGENCES)]
    for c, analytique, sim, resume in detail_base:
        t2.append(f"| {c} | {pct(analytique['occupation'])} / {pct(sim['occupation'])} | " + " | ".join(
            f"{minutes(resume[u]['moyenne'])} / {pct(resume[u]['dans_le_delai'])}" for u in URGENCES) + " |")

    # Agents postés : peut-on tenir le délai URGENT en plaçant des agents plutôt qu'en en ajoutant ?
    politiques = {
        "Application actuelle (aucun poste)": {},
        "1 agent posté aux Urgences": {"postes": (URGENCES_NOEUD,)},
        "1 agent posté aux Urgences, réservé aux URGENT": {"postes": (URGENCES_NOEUD,), "reserve": True},
        "2 agents postés (hall RDC, palier de l'étage)": {"postes": (HALL_RDC, PALIER_ETAGE)},
        "2 agents postés, réservés aux URGENT": {"postes": (HALL_RDC, PALIER_ETAGE), "reserve": True},
    }
    debit_base = H.demandes_par_heure("journee", 3)
    t3 = ["| Agents | Organisation | URGENT en 3 min (départ au hasard) | URGENT en 3 min (départ surtout "
          "des Urgences) | HAUTE / MOYENNE / BASSE dans le délai |", "|---|---|---|---|---|"]
    for c in (4, 5, 6, 8):
        for nom, options in politiques.items():
            r = resumer(simuler(debit_base, c, heures, graine=c, **options)["attentes"])
            r2 = resumer(simuler(debit_base, c, heures, graine=c, sources_urgent=SOURCES_URGENT_CONCENTREES,
                                 **options)["attentes"])
            gras = "**" if respecte_objectif(r) and r["URGENT"]["dans_le_delai"] >= 0.90 else ""
            t3.append(f"| {c} | {nom} | {gras}{pct(r['URGENT']['dans_le_delai'])}{gras} "
                      f"| {pct(r2['URGENT']['dans_le_delai'])} | "
                      + " / ".join(pct(r[u]["dans_le_delai"]) for u in ("HAUTE", "MOYENNE", "BASSE")) + " |")

    texte = "\n".join([
        "# Résultats de l'analyse de la file d'attente",
        "",
        f"Généré par `python analyse_file_attente.py` : {heures} h simulées par configuration, "
        f"hypothèses de `hypotheses.py` (HOGIP, annuaires MSAS 2020-2021).",
        f"Plan de l'hôpital : {len(SERVICES)} services, trajet moyen d'un service à un autre "
        f"{TRAJET_MOYEN_MIN:.1f} min (de {min(DISTANCES[a][b] for a, b in PAIRES):.1f} à "
        f"{max(DISTANCES[a][b] for a, b in PAIRES):.1f} min).",
        "",
        "## Agents nécessaires par période",
        "",
        "Critère : 95 % des missions HAUTE, MOYENNE et BASSE prises en charge dans leur délai garanti "
        "(8, 15 et 30 min). L'attente est mesurée de la demande au scan du bracelet.",
        "",
        *t1,
        "",
        "## Détail : 3 transports par séjour, journée",
        "",
        *t2,
        "",
        "## Agents postés : tenir le délai URGENT",
        "",
        "3 transports par séjour, journée. Un agent posté revient attendre à son poste après chaque mission ; "
        "« réservé » : il ne prend que les URGENT. En gras : 90 % des URGENT et 95 % des autres dans le délai.",
        "La colonne « départ surtout des Urgences » est une variante (60 % Urgences, 20 % Réanimation, "
        "20 % Bloc) : aucune donnée publiée ne donne l'origine des transports urgents.",
        "",
        *t3,
        "",
    ])
    (RACINE / "analyse_file_attente_resultats.md").write_text(texte, encoding="utf-8")
    print(texte)
    print(f"Détail de chaque configuration : {DOSSIER_RESULTATS / 'analyse_file_attente.csv'}")


if __name__ == "__main__":
    main()
