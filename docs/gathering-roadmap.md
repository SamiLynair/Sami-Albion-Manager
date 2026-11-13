# Sami Albion Manager v0.5.0 — Récolte et Socket natif (bêta)

## Architecture

Trois modes indépendants sont disponibles dans la page **Récolte** :

- **Démonstration** : sessions et récoltes fictives pour tester les boutons.
  Base locale `gathering_demo.sqlite3`.
- **Statistics Analysis • fichier local** : lecture seule de `Gathering.json`,
  sans lancer de capture dans Sami ; les chiffres sont actualisés après les
  sauvegardes de Statistics Analysis.
- **Socket natif • bêta** : collecte Windows indépendante via sockets IPv4
  bruts (administrateur), décodage Photon / Protocol18, identification du
  personnage par JoinResponse, détection HarvestFinished, sauvegarde SQLite
  séparée dans `gathering_live.sqlite3`.

Pas d'overlay et aucune modification du processus du jeu.

## Source du nom des ressources

Les événements Photon transmettent un **index numérique d'objet**. La bêta
résout ces identifiants à l'aide de la liste `IndexedItems.json` :
`%LOCALAPPDATA%\StatisticsAnalysisTool\Instances\<instance>\GameFiles\IndexedItems.json`.

C'est une référence locale **utilisée comme table de correspondance**.
Statistics Analysis ne doit pas être ouvert pendant l'utilisation du mode
Socket natif. Si le fichier n'est pas trouvé, cliquer sur le bouton
**IndexedItems.json** dans la page Récolte et le sélectionner manuellement.

L'index de ressources devra ensuite être embarqué directement dans Sami
pour supprimer cette dépendance d'installation préalable.

## Comment tester Socket sur Windows

1. Télécharger le ZIP de la branche `feature/gathering-session-core`.
2. Extraire le ZIP et lancer `compiler_apercu_v0_5_windows.bat`.
3. Le script lance les tests, compile et ouvre
   `dist\Sami Albion Manager 0.5 Apercu.exe` sans publier de release.
4. Pour essayer la capture, fermer l'aperçu, puis relancer **cet EXE**
   avec **Exécuter en tant qu'administrateur**.
5. Dans **Récolte**, choisir **Socket natif • bêta**, sélectionner l'adresse
   IPv4 locale si nécessaire, puis cliquer **Démarrer Socket**.
6. Se connecter à Albion après le démarrage de la capture afin que Sami puisse
   voir la réponse Join et identifier le personnage local.
7. Récolter quelques ressources, puis vérifier les quantités sur le tableau.
8. Utiliser **Arrêter Socket** pour terminer et sauvegarder la session.

## Ce qui est implémenté

- Lecture Windows IPv4 / UDP avec filtrage de ports Photon.
- Lecture des commandes Photon fiables, non fiables et fragmentées.
- Décodeur borné Protocol18 et reconnaissance de Join + HarvestFinished.
- Comptage normal + bonus de récolte + bonus Premium.
- Filtre sur l'identifiant du personnage local.
- Déduplication des retransmissions par identification de commande réseau.
- Mise à jour du tableau PySide6 via signaux Qt.
- Persistance locale des sessions.
- Tests synthétiques pour les paquets, les fragments, les identifiants,
  les numéros d'objets et la couche réseau.

## Limites actuelles

- **Bêta non encore validée contre du trafic réel sur Windows.** Des cas
  particuliers du protocole Photon et des évolutions du jeu restent possibles.
- Mode Socket actuellement **IPv4 uniquement** ; IPv6 à intégrer ensuite.
- Après activation du Socket, une nouvelle connexion de personnage permet de
  détecter son identifiant ; démarrer la capture en étant déjà connecté peut
  laisser la page en attente.
- Les types Protocol18 peu courants ne sont pas tous implémentés.
- Les index absents du dictionnaire sont stockés sous `INDEX_<numéro>`,
  sans inventer de nom d'objet.
- Les estimations économiques et les filtres avancés viendront après la
  validation de la collecte sur une vraie session.

## Vérification automatique

```text
python -m unittest discover -s tests -v
```

Le workflow `.github/workflows/gathering-pr-check.yml` peut exécuter ces
tests sur Windows. Le script d'aperçu les lance avant la compilation locale.

La version publique `main` reste v0.4.11. Cette bêta v0.5.0 n'est ni
fusionnée ni publiée comme mise à jour générale.
