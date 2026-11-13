# Module Récolte — premier jalon (branche expérimentale)

## Objectif

Suivre des sessions de récolte Albion Online sans intervenir dans le jeu.
Le moteur est écrit en Python (bibliothèque standard) et stocke les résultats
dans une base SQLite locale. Il n'est **pas encore relié à l'interface**.

## Conformité : pas de capture du jeu

Les conditions d'Albion Online en vigueur au 31 août 2026, §13.3, interdisent
notamment les logiciels qui interceptent ou capturent des données en lien
avec le jeu. Le fait qu'un autre tracker existe ou fonctionne ne vaut pas
autorisation pour Sami Albion Manager.

Référence : https://albiononline.com/terms_and_conditions

**Ce jalon n'inclut aucun** sniffer de paquets, accès mémoire au client,
injection, automatisation de gameplay, surveillance de processus, ni
connexion à un serveur du jeu. Il n'importe que des événements explicitement
fournis dans les tests ou par un utilisateur. Toute future source automatique
devra faire l'objet d'une autorisation claire de Sandbox Interactive ou
s'appuyer sur une interface expressément autorisée.

## Ce qui fonctionne

- Création et fermeture de sessions par personnage.
- Comptage détaillé : récolte normale, bonus récolteur et bonus Premium.
- Totaux par ressource et par session, durée et ressources/heure.
- Estimation de valeur à partir de prix *fournis*, sans requête réseau.
- Distinction des ressources sans prix connu (pas de bénéfice fictif).
- Déduplication par identifiant d'événement.
- Base SQLite persistante après redémarrage.
- Tests hors jeu : `python -m unittest tests/test_gathering_sessions.py -v`.

## Contrat d'entrée (exemple sans capture)

```python
from pathlib import Path
from samialbion.gathering_sessions import GatheringStore

with GatheringStore(Path.home() / "SamiAlbionManager" / "gathering.db") as store:
    session_id = store.start_session("PersonnageExemple")
    store.add_event(session_id, "T6_ORE", 3, gathering_bonus=1, premium_bonus=1)
    report = store.summary(session_id, unit_prices={"T6_ORE": 100})
    assert report.total_resources == 5
    store.end_session(session_id)
```

## À faire

1. Définir la source de données autorisée (validation avec Sandbox Interactive).
2. Ajouter une interface « Récolte » en PySide6 utilisant la base locale.
3. Ajouter filtres par type, tier, enchantement et session, puis valeurs marché.
4. Créer ensuite le tableau de bord synthétique à partir des mêmes sessions.

**Ne pas fusionner ce jalon avec une fonctionnalité de capture non autorisée.**
