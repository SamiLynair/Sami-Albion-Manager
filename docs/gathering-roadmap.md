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
- Page PySide6 « Récolte » accessible depuis le menu gauche sur cette branche :
  création/fin de session, choix d'historique, indicateurs de quantité,
  actions de récolte, durée et ressources/heure.
- Affichage des noms et icônes originaux par le catalogue embarqué.
- Simulation explicite via « + Simuler une récolte » ; aucune lecture en jeu.
- Sessions fictives isolées dans `gathering_demo.sqlite3` sous le répertoire
  applicatif utilisateur ; les futures données réelles devront utiliser
  une base séparée.
- Tests UI : `python -m unittest tests/test_gathering_page.py -v`
  (PySide6 et ressources embarquées nécessaires).

## Lecture du fichier Statistics Analysis (optionnelle)

Une solution de synchronisation **en lecture seule** existe désormais sur la page
« Récolte ». Elle importe le fichier `Gathering.json` que Statistics Analysis
écrit lui-même. Le fichier source n'est jamais modifié.

- Dans Sami, choisir **Statistics Analysis • fichier local**.
- Sami recherche d'abord les chemins Windows connus dans
  `%LOCALAPPDATA%/StatisticsAnalysisTool/Instances/*/UserData-EUROPE/Gathering.json`
  (et variantes AMERICA/ASIA). Sinon, cliquer sur **Choisir Gathering.json**.
- Les sessions, personnages, ressources normales et bonus sont affichés.
- Le fichier est relu automatiquement si sa date de modification change
  (vérification toutes les 5 secondes).
- Selon le code Statistics Analysis actuel, l'enregistrement des récoltes sur
  disque se produit notamment après **10 événements**, pas nécessairement à
  chaque récolte : la synchronisation ne peut donc pas être instantanée.
- Les durées et gains/heure de ces snapshots sont affichés **indisponibles** :
  les timestamps sauvegardés par SA ne donnent pas un début et une fin de
  session fiables pour ce calcul.
- Cette solution **nécessite Statistics Analysis installé et utilisé
  séparément**. Elle ne remplace pas son moteur Socket.
- Elle ne garantit pas que l'utilisation de Statistics Analysis soit autorisée
  par Sandbox Interactive ; la clarification des conditions reste nécessaire.

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
2. Tester visuellement la page « Récolte » et ses commandes sur Windows.
3. Ajouter filtres par type, tier, enchantement et session, puis valeurs marché.
4. Créer ensuite le tableau de bord synthétique à partir des mêmes sessions.

**Ne pas fusionner ce jalon avec une fonctionnalité de capture non autorisée.**

## Tester l'affichage de la v0.5.0 sur Windows

Cette prévisualisation ne remplace pas la version stable v0.4.11.

1. Ouvrir la branche `feature/gathering-session-core` sur GitHub et
   télécharger **Code → Download ZIP** (pas le ZIP de `main`).
2. Extraire **tout** le ZIP dans un nouveau dossier, distinct de l'installation.
3. Double-cliquer sur `compiler_apercu_v0_5_windows.bat` : il installe
   les dépendances Python dans `.venv-apercu`, lance les tests, compile
   puis ouvre `dist/Sami Albion Manager 0.5 Apercu.exe`.
4. Dans l'application, ouvrir « Récolte » dans le menu latéral.
5. Tester une session fictive et le bouton « Simuler une récolte ».
6. Optionnel : dans la liste des sources, sélectionner
   « Statistics Analysis • fichier local ». Si SA a déjà enregistré un
   `Gathering.json`, la page tente de le retrouver automatiquement ;
   sinon sélectionner manuellement le fichier. Cette option ne démarre
   pas Statistics Analysis et n'intercepte aucun paquet.

Le compilateur d'aperçu **n'utilise pas `gh release create`**, ne modifie pas
`main` et ne remplace pas l'exécutable déjà installé. Les mises à jour
automatiques sont désactivées pendant ce test. La publication officielle
sera préparée seulement après contrôle du rendu et des tests Windows.

