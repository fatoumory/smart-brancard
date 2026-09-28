# Admission des patients : génération de l'IPP et du bracelet, détection des patients déjà connus.
# Dans le prototype, ce service simule le logiciel d'admission de l'hôpital ;
# en production, un connecteur (HL7 / FHIR) pourrait appeler admettre_patient à sa place.

from uuid import uuid4

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models.enums import StatutIdentite
from models.patient import Patient
from schemas.patient import PatientAdmission, PatientIdentite


class PatientsSimilaires(Exception):
    """Un ou plusieurs patients semblables existent déjà : il faut choisir ou confirmer"""

    def __init__(self, patients: list[Patient]):
        super().__init__("Patient(s) semblable(s) déjà connu(s)")
        self.patients = patients


def generer_ipp(patient_id: int) -> str:
    """IPP sur 8 chiffres, déduit de l'identifiant (unique par construction)"""
    return f"{patient_id:08d}"


def chercher_similaires(db: Session, nom: str, prenom: str, date_naissance, exclure_id: int | None = None) -> list[Patient]:
    """Patients de même nom et prénom (sans tenir compte des majuscules).
    Si les deux dates de naissance sont connues et différentes, ce sont deux personnes distinctes."""
    requete = db.query(Patient).filter(
        func.lower(Patient.nom) == nom.lower(),
        func.lower(Patient.prenom) == prenom.lower(),
    )
    if date_naissance is not None:
        requete = requete.filter(or_(Patient.date_naissance == date_naissance,
                                    Patient.date_naissance.is_(None)))
    # Lors d'une correction d'identité, le patient ne doit pas se trouver lui-même
    if exclure_id is not None:
        requete = requete.filter(Patient.id != exclure_id)

    return requete.order_by(Patient.id).all()


def admettre_patient(db: Session, donnees: PatientAdmission) -> Patient:
    """Enregistre un patient à son arrivée et lui attribue un IPP et un bracelet.
    Lève PatientsSimilaires si un patient semblable existe et que la création n'est pas confirmée."""

    # 1. Patient qui revient ? (impossible à vérifier pour une identité inconnue)
    if not donnees.identite_inconnue and not donnees.confirmer_nouveau:
        similaires = chercher_similaires(db, donnees.nom, donnees.prenom, donnees.date_naissance)
        if similaires:
            raise PatientsSimilaires(similaires)

    # 2. Création avec des valeurs temporaires uniques : l'IPP définitif dépend de l'id,
    #    qui n'est connu qu'après l'envoi à la base (flush)
    temporaire = f"TMP-{uuid4().hex}"
    patient = Patient(
        id_hospitalisation=temporaire,
        code_bracelet=temporaire,
        nom=donnees.nom or "INCONNU",
        prenom=donnees.prenom or "X",
        date_naissance=donnees.date_naissance,
        sexe=donnees.sexe,
        statut_identite=(StatutIdentite.PROVISOIRE if donnees.identite_inconnue
                        else StatutIdentite.VALIDEE),
    )
    db.add(patient)
    db.flush()

    # 3. IPP définitif et bracelet (le QR encode l'IPP)
    ipp = generer_ipp(patient.id)
    patient.id_hospitalisation = ipp
    patient.code_bracelet = f"QR-{ipp}"
    if donnees.identite_inconnue:
        # Identité provisoire unique : "INCONNU X-00000148"
        patient.nom = "INCONNU"
        patient.prenom = f"X-{ipp}"

    db.commit()
    db.refresh(patient)
    return patient

def rechercher_patients(db: Session, recherche: str, limite: int = 20) -> list[Patient]:
    """Recherche par nom, prénom ou IPP. Chaque mot doit apparaître quelque part :
    « dup jea » trouve Jean Dupont, « 00000148 » trouve le patient par son IPP."""
    requete = db.query(Patient)
    for mot in recherche.split():
        motif = f"%{mot}%"
        requete = requete.filter(or_(
            Patient.nom.ilike(motif),
            Patient.prenom.ilike(motif),
            Patient.id_hospitalisation.ilike(motif),
        ))
    return requete.order_by(Patient.nom, Patient.prenom, Patient.id).limit(limite).all()


def valider_identite(db: Session, patient: Patient, donnees: PatientIdentite) -> Patient:
    """Remplace l'identité (provisoire ou erronée) par l'identité confirmée.
    L'IPP et le bracelet ne changent pas : les missions déjà liées au patient restent valables.
    Lève PatientsSimilaires si l'identité correspond à un autre patient déjà connu."""
    if not donnees.confirmer_nouveau:
        similaires = chercher_similaires(db, donnees.nom, donnees.prenom,
                                        donnees.date_naissance, exclure_id=patient.id)
        if similaires:
            raise PatientsSimilaires(similaires)

    patient.nom = donnees.nom
    patient.prenom = donnees.prenom
    if donnees.date_naissance is not None:
        patient.date_naissance = donnees.date_naissance
    if donnees.sexe is not None:
        patient.sexe = donnees.sexe
    patient.statut_identite = StatutIdentite.VALIDEE

    db.commit()
    db.refresh(patient)
    return patient

