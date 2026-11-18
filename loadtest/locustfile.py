# loadtest/locustfile.py
# Tests de charge du Sprint 5 : brancardiers, médecin et régulateur virtuels.
#
# Deux usages :
#   - scénario « realiste » : la charge de l'Hôpital Général Idrissa Pouye (hypotheses.py), avec
#     8 brancardiers. Sert à mesurer l'attente avant prise en charge par niveau d'urgence et à la
#     comparer au modèle de file d'attente ;
#   - scénario « charge » : 50 brancardiers et une demande bien plus forte, pour vérifier que le
#     serveur tient (temps de réponse, erreurs).
#
# Le temps est accéléré (ACCEL) : une mission de 12 min dure 12/ACCEL min, et les demandes arrivent
# ACCEL fois plus vite. Les rapports entre arrivées et durées sont conservés, donc les files d'attente
# aussi ; les attentes mesurées sont remises à l'échelle réelle (× ACCEL) dans les résultats.
#
# Lancement : voir loadtest/README.md

from locust import HttpUser, LoadTestShape, between, events, task  # en premier : Locust adapte le réseau avant les autres imports

import csv
import itertools
import json
import os
import random
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import hypotheses as H

# --- Paramètres (variables d'environnement) --------------------------------------------------
SCENARIO = os.getenv("SCENARIO", "realiste")
PRESETS = {
    "realiste": {"NB_AGENTS": 8, "ACCEL": 10, "PERIODE": "journee"},
    "charge": {"NB_AGENTS": 50, "ACCEL": 60, "PERIODE": "pic"},
}
PRESET = PRESETS[SCENARIO]
NB_AGENTS = int(os.getenv("NB_AGENTS", PRESET["NB_AGENTS"]))
ACCEL = float(os.getenv("ACCEL", PRESET["ACCEL"]))
PERIODE = os.getenv("PERIODE", PRESET["PERIODE"])
TRANSPORTS = int(os.getenv("TRANSPORTS", "3"))
# Durée du test en minutes réelles, comptée après la préparation (comptes, patients)
DUREE_MIN = float(os.getenv("DUREE_MIN", "6"))
REG_UTILISATEUR = os.getenv("REG_UTILISATEUR", "")
REG_MOT_DE_PASSE = os.getenv("REG_MOT_DE_PASSE", "")

MOT_DE_PASSE_TEST = "LocustTest2026"
MEDECIN_TEST = "locust.medecin@smartbrancard.local"
NB_PATIENTS = 60

# Demandes par seconde (temps accéléré)
DEBIT_PAR_S = H.demandes_par_heure(PERIODE, TRANSPORTS) * ACCEL / 3600
# Rafraîchissement du téléphone (GET /missions/moi) et renvoi du badge quand l'agent attend
INTERVALLE_SONDAGE_S = 1 if SCENARIO == "charge" else 2
INTERVALLE_BADGE_S = 60

DOSSIER_RESULTATS = Path(__file__).parent / "resultats"


def s_reelles(minutes_hopital: float) -> float:
    """Durée réelle d'attente pour une durée exprimée en minutes « d'hôpital » (temps accéléré)"""
    return minutes_hopital * 60 / ACCEL


# --- État partagé, préparé au début du test --------------------------------------------------
class Partage:
    reg_entetes: dict = {}
    medecin_id: int | None = None
    services: list[int] = []
    patients: list[int] = []
    debut: datetime | None = None


compteur_agents = itertools.count(1)
compteur_patients = itertools.count()


def connexion(hote: str, utilisateur: str, mot_de_passe: str) -> dict:
    r = requests.post(f"{hote}/auth/login", data={"username": utilisateur, "password": mot_de_passe}, timeout=30)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def creer_compte(hote: str, reg: dict, nom_utilisateur: str, role: str, nom: str) -> None:
    """Crée le compte s'il n'existe pas déjà (un compte existant est simplement réutilisé)"""
    r = requests.post(f"{hote}/auth/register", headers=reg, timeout=30, json={
        "nom_utilisateur": nom_utilisateur, "prenom": "Locust", "nom": nom,
        "mot_de_passe": MOT_DE_PASSE_TEST, "role": role})
    if r.status_code not in (201, 400, 409):
        r.raise_for_status()


def annuler_missions_de_test(hote: str) -> int:
    """Annule les missions encore actives créées par le médecin de test (essais précédents)"""
    r = requests.get(f"{hote}/missions", headers=Partage.reg_entetes, timeout=60, params={
        "statut": ["EN_ATTENTE", "PROPOSE", "ACCEPTE", "EN_TRANSIT"], "limite": 500})
    r.raise_for_status()
    annulees = 0
    for m in r.json():
        if m["prescripteur_id"] == Partage.medecin_id:
            if requests.put(f"{hote}/missions/{m['id']}/annuler", headers=Partage.reg_entetes,
                            timeout=30).ok:
                annulees += 1
    return annulees


@events.test_start.add_listener
def preparer(environment, **_):
    hote = environment.host
    if not REG_UTILISATEUR or not REG_MOT_DE_PASSE:
        raise SystemExit("Renseignez REG_UTILISATEUR et REG_MOT_DE_PASSE (compte régulateur)")
    Partage.reg_entetes = connexion(hote, REG_UTILISATEUR, REG_MOT_DE_PASSE)

    # Comptes de test : un médecin et les brancardiers
    creer_compte(hote, Partage.reg_entetes, MEDECIN_TEST, "MEDECIN", "Medecin")
    for i in range(1, NB_AGENTS + 1):
        creer_compte(hote, Partage.reg_entetes, f"locust.agent{i:02d}@smartbrancard.local", "BRANCARDIER",
                     f"Agent{i:02d}")
    medecin = connexion(hote, MEDECIN_TEST, MOT_DE_PASSE_TEST)
    Partage.medecin_id = requests.get(f"{hote}/auth/me", headers=medecin, timeout=30).json()["id"]

    # Lieux de départ et d'arrivée possibles : les services du graphe
    r = requests.get(f"{hote}/noeuds", headers=Partage.reg_entetes, params={"type_noeud": "SERVICE"}, timeout=30)
    Partage.services = [n["id"] for n in r.json()]

    # Patients de test : identité inconnue, pour ne jamais créer de faux noms ni d'homonymes
    Partage.patients = []
    for _ in range(NB_PATIENTS):
        r = requests.post(f"{hote}/patients", headers=medecin, json={"identite_inconnue": True}, timeout=30)
        r.raise_for_status()
        Partage.patients.append(r.json()["id"])

    annulees = annuler_missions_de_test(hote)
    Partage.debut = datetime.now(timezone.utc)
    print(f"[Smart-Brancard] Scénario {SCENARIO} : {NB_AGENTS} agents, période {PERIODE}, "
          f"{TRANSPORTS} transports/séjour, accélération x{ACCEL:g}, "
          f"{DEBIT_PAR_S * 3600 / ACCEL:.1f} demandes/h d'hôpital, {DUREE_MIN:g} min réelles "
          f"({DUREE_MIN * ACCEL / 60:.1f} h d'hôpital) ; {annulees} anciennes missions annulées")


# --- Profil de charge ------------------------------------------------------------------------
class TousLesActeurs(LoadTestShape):
    """Lance d'un coup tous les acteurs du scénario (agents, médecin, régulateur) pendant DUREE_MIN.
    Remplace les options -u, -r et --run-time de Locust : le chronomètre part après la préparation."""

    def tick(self):
        total = NB_AGENTS + 2
        if Partage.debut and (datetime.now(timezone.utc) - Partage.debut).total_seconds() > DUREE_MIN * 60:
            return None
        return total, total


# --- Utilisateurs virtuels -------------------------------------------------------------------
class Medecin(HttpUser):
    """Le service qui demande des transports : arrivées aléatoires (processus de Poisson)"""
    fixed_count = 1

    def wait_time(self):
        return random.expovariate(DEBIT_PAR_S)

    def on_start(self):
        self.entetes = connexion(self.host, MEDECIN_TEST, MOT_DE_PASSE_TEST)

    @task
    def demander_transport(self):
        source, destination = random.sample(Partage.services, 2)
        urgence = random.choices(list(H.PART_URGENCES), weights=list(H.PART_URGENCES.values()))[0]
        patient = Partage.patients[next(compteur_patients) % len(Partage.patients)]
        self.client.post("/missions/create", headers=self.entetes, name="/missions/create", json={
            "patient_id": patient, "noeud_source_id": source, "noeud_destination_id": destination,
            "niveau_urgence": urgence})


class Regulateur(HttpUser):
    """Le dashboard du régulateur, rechargé régulièrement (en plus du temps réel)"""
    fixed_count = 1
    wait_time = between(8, 12)

    def on_start(self):
        self.entetes = connexion(self.host, REG_UTILISATEUR, REG_MOT_DE_PASSE)

    @task
    def dashboard(self):
        self.client.get("/missions?limite=500", headers=self.entetes, name="/missions")
        self.client.get("/utilisateurs?role=BRANCARDIER", headers=self.entetes, name="/utilisateurs")
        self.client.get("/missions/saturation", headers=self.entetes, name="/missions/saturation")
        self.client.get("/alertes?traitee=false", headers=self.entetes, name="/alertes")


class Brancardier(HttpUser):
    """Un agent et son téléphone. Son badge est capté par le récepteur de la salle où il se trouve
    (POST /detections/badge, envoyé avec le compte régulateur comme le ferait le simulateur)."""
    fixed_count = NB_AGENTS
    wait_time = between(INTERVALLE_SONDAGE_S * 0.8, INTERVALLE_SONDAGE_S * 1.2)

    def on_start(self):
        numero = next(compteur_agents)
        self.entetes = connexion(self.host, f"locust.agent{numero:02d}@smartbrancard.local", MOT_DE_PASSE_TEST)
        self.id = self.client.get("/auth/me", headers=self.entetes, name="/auth/me").json()["id"]
        self.lieu = random.choice(Partage.services)
        self.dernier_badge = 0.0
        self.badge(self.lieu)
        # 409 attendu si une mission lui a déjà été proposée (un agent est disponible dès sa création)
        with self.client.patch("/utilisateurs/me/statut", headers=self.entetes, json={"statut": "DISPONIBLE"},
                               name="/utilisateurs/me/statut", catch_response=True) as r:
            if r.status_code == 409:
                r.success()

    def badge(self, lieu: int):
        self.lieu = lieu
        self.dernier_badge = time.monotonic()
        self.client.post("/detections/badge", headers=Partage.reg_entetes, name="/detections/badge",
                         json={"brancardier_id": self.id, "noeud_id": lieu})

    @task
    def telephone(self):
        r = self.client.get("/missions/moi", headers=self.entetes, name="/missions/moi")
        mission = r.json() if r.ok else None
        if not mission:
            # En attente : le badge continue d'être capté, la position reste récente
            if time.monotonic() - self.dernier_badge > INTERVALLE_BADGE_S:
                self.badge(self.lieu)
            return

        mid = mission["id"]
        if mission["statut"] == "PROPOSE":
            time.sleep(random.uniform(*H.REPONSE_AGENT_S) / ACCEL)
            if random.random() < H.PART_ACCEPTATIONS:
                self.client.put(f"/missions/{mid}/accept", headers=self.entetes, name="/missions/[id]/accept")
            else:
                # Retenu par une autre urgence : il refuse, puis revient quand il a fini (15 min)
                self.client.put(f"/missions/{mid}/refuse", headers=self.entetes, name="/missions/[id]/refuse",
                                json={"motif": "URGENCE_PRIORITAIRE"})
                time.sleep(s_reelles(15))
                self.client.patch("/utilisateurs/me/statut", headers=self.entetes,
                                  json={"statut": "DISPONIBLE"}, name="/utilisateurs/me/statut")
                self.badge(self.lieu)

        elif mission["statut"] == "ACCEPTE":
            # Trajet jusqu'au patient, détection du badge au départ, puis scan du bracelet dès qu'il est
            # près du patient : c'est la prise en charge (passage EN_TRANSIT), qui compte pour le délai garanti
            time.sleep(s_reelles(mission.get("temps_agent_min") or 2))
            self.badge(mission["noeud_source_id"])
            self.client.post(f"/missions/{mid}/scan-depart", headers=self.entetes, name="/missions/[id]/scan-depart",
                             json={"code_bracelet": f"QR-{mission['patient_ipp']}"})

        elif mission["statut"] == "EN_TRANSIT":
            # Installation du patient, transport, détection du badge à l'arrivée, remise, puis « Arrivé »
            time.sleep(s_reelles(H.DUREE_INSTALLATION_MIN + (mission.get("duree_estimee") or 5)))
            self.badge(mission["noeud_destination_id"])
            time.sleep(s_reelles(H.DUREE_REMISE_MIN))
            self.client.post(f"/missions/{mid}/arrivee", headers=self.entetes, name="/missions/[id]/arrivee")


# --- Résultats -------------------------------------------------------------------------------
def lire_date(texte: str | None) -> datetime | None:
    if not texte:
        return None
    d = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


@events.test_stop.add_listener
def exporter(environment, **_):
    """Attente avant prise en charge de chaque mission du test, remise à l'échelle réelle"""
    hote = environment.host
    missions = []
    for urgence in H.PART_URGENCES:
        r = requests.get(f"{hote}/missions", headers=Partage.reg_entetes, timeout=60,
                         params={"niveau_urgence": urgence, "limite": 500})
        missions += [m for m in r.json() if m["prescripteur_id"] == Partage.medecin_id
                     and lire_date(m["date_creation"]) >= Partage.debut]

    lignes = []
    for m in missions:
        creation, prise = lire_date(m["date_creation"]), lire_date(m.get("date_prise_en_charge"))
        attente_min = (prise - creation).total_seconds() * ACCEL / 60 if prise else None
        lignes.append({
            "id": m["id"], "urgence": m["niveau_urgence"], "statut": m["statut"],
            "date_creation": m["date_creation"], "date_prise_en_charge": m.get("date_prise_en_charge"),
            "attente_min_hopital": round(attente_min, 2) if attente_min is not None else "",
            "delai_garanti_min": H.DELAIS_GARANTIS_MIN[m["niveau_urgence"]],
            "dans_le_delai": "" if attente_min is None else attente_min <= H.DELAIS_GARANTIS_MIN[m["niveau_urgence"]],
        })

    synthese = {"scenario": SCENARIO, "agents": NB_AGENTS, "periode": PERIODE, "transports_par_sejour": TRANSPORTS,
                "acceleration": ACCEL, "demandes_par_heure": round(H.demandes_par_heure(PERIODE, TRANSPORTS), 2),
                "par_urgence": {}}
    for urgence, delai in H.DELAIS_GARANTIS_MIN.items():
        attentes = [l["attente_min_hopital"] for l in lignes if l["urgence"] == urgence and l["attente_min_hopital"] != ""]
        total = sum(1 for l in lignes if l["urgence"] == urgence)
        synthese["par_urgence"][urgence] = {
            "missions": total,
            "prises_en_charge": len(attentes),
            "attente_moyenne_min": round(statistics.mean(attentes), 2) if attentes else None,
            "attente_p90_min": round(statistics.quantiles(attentes, n=10)[-1], 2) if len(attentes) >= 10 else None,
            "part_dans_le_delai": round(sum(a <= delai for a in attentes) / len(attentes), 3) if attentes else None,
        }

    DOSSIER_RESULTATS.mkdir(exist_ok=True)
    nom = f"{SCENARIO}_{PERIODE}_{NB_AGENTS}agents_{TRANSPORTS}tps_{datetime.now():%Y%m%d_%H%M}"
    with open(DOSSIER_RESULTATS / f"{nom}_missions.csv", "w", newline="", encoding="utf-8") as f:
        if lignes:
            ecrivain = csv.DictWriter(f, fieldnames=list(lignes[0]))
            ecrivain.writeheader()
            ecrivain.writerows(lignes)
    (DOSSIER_RESULTATS / f"{nom}_synthese.json").write_text(json.dumps(synthese, indent=2, ensure_ascii=False),
                                                            encoding="utf-8")
    print(json.dumps(synthese, indent=2, ensure_ascii=False))

    annulees = annuler_missions_de_test(hote)
    print(f"[Smart-Brancard] Résultats dans loadtest/resultats/{nom}_* ; {annulees} missions en cours annulées")
