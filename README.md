# Sami Albion Manager · v0.5.0 (aperçu expérimental)

**Mon carnet d'artisan** est un logiciel Windows personnel pour Albion Online : catalogue, craft et, dans cette branche expérimentale, suivi local des récoltes.

## Essayer la page Récolte de la v0.5.0

Cette version est un **aperçu non publié** ; `main` reste en v0.4.11.

Depuis la branche `feature/gathering-session-core`, télécharger **Code → Download ZIP**, extraire entièrement l'archive, puis lancer `compiler_apercu_v0_5_windows.bat` sous Windows. Le script exécute les tests, compile puis ouvre un exécutable distinct : `dist/Sami Albion Manager 0.5 Apercu.exe`. Il ne publie aucune release et ne remplace pas la version installée.

Ouvrir ensuite **Récolte**, tester une session fictive, ou sélectionner **Statistics Analysis • fichier local** pour importer en lecture seule un `Gathering.json` déjà enregistré par le logiciel tiers. **Aucune capture Socket n'est intégrée à Sami à ce stade.** Les mises à jour du tableau reflètent les sauvegardes du fichier, potentiellement différées.

## Fonctions présentes

- **Catalogue d'objets** : 12 503 références provenant d'un instantané du projet `ao-data/ao-bin-dumps` : équipements, ressources, matières raffinées, potions, nourriture, montures, agriculture, artefacts, mobilier et autres objets.
- **Table de Craft (v0.4.0)** : nouvel onglet avec recherche d'objets craftables, filtrage par tier et enchantement, recettes intégrées hors ligne (8 859 recettes issues de `ao-data/ao-bin-dumps`), quantités nécessaires et images des ressources. Saisis manuellement les prix d'achat et de vente pour calculer la rentabilité ; les prix sont conservés sur ton PC.
- **Table de Craft (v0.4.1)** : choisis directement le nombre **d'unités à produire** : les fabrications sont arrondies au lot supérieur et toutes les quantités d'ingrédients sont multipliées automatiquement. Option de déduction de **6,5 %** de la valeur vendue, coût d'artisan **par fabrication**, et pourcentage manuel de retour des ressources. Le panneau affiche le coût d'achat initial, la valeur des ressources récupérées, les frais et le bénéfice final estimé. Les options sont mémorisées.
- **Recherche française/anglaise** par nom d'objet. Les identifiants techniques ne sont pas affichés.
- **Classement comme au marché d'Albion** : menu compact en trois niveaux, par exemple **Armes → Arc → Arc de guerre**, ou **Fabrication → Ressources raffinées → Lingot**. Les catégories et sous-catégories proviennent des données de jeu `items.xml` ; les familles d'objets sont déduites localement de leurs noms. Les nouveautés sans correspondance dans ces données utilisent des catégories de remplacement.
- **Filtres** : catégorie, tier (T1 à T8), enchantement (.0 à .4) et qualité (normale à exceptionnelle) pour les équipements où elle s'applique.
- **Réinitialiser les filtres** : un bouton à droite de la recherche efface le texte, la catégorie, le tier, l'enchantement et la qualité en un clic.
- **Style du marché** : recherche et filtres couleur parchemin, touches dorées et tableau clair sur fond de bois sombre, sans ajouter de tarifs ou de connexion au jeu.
- **Bandeau latéral harmonisé** : bois brun foncé, boutons bronze et or, calculatrice et panneau serveur assortis au catalogue.
- **Retouches visuelles** : icônes sans carré sombre opaque, alignement du champ des catégories et listes déroulantes aux textes clairs et contrastés.
- **Sélection discrète** : la ligne de l'objet est mise en évidence sans recolorer son image.
- **Recherche au clavier corrigée** : les touches Retour arrière et Supprimer fonctionnent normalement ; les raccourcis de la calculatrice ne s'activent que lorsque celle-ci est sélectionnée.
- **Images des objets** : **11 803 illustrations** issues du service de rendu du jeu, récupérées une seule fois pendant le développement et enregistrées localement au format WEBP dans `samialbion/assets/item_icons.zip`. Les variantes de qualité réutilisent l'illustration de base et affichent un cadre coloré et le niveau choisi. Les 700 identifiants sans rendu disponible gardent un pictogramme « ? », jamais une fausse image.
- **Calculatrice** fermée au démarrage : elle se déploie uniquement en cliquant sur son volet en bas de la barre latérale. Opérations courantes et utilisation au clavier.
- **Paramètres** : roue crantée près de « Made by Sami », ouvrant une page dédiée qui héberge désormais le bouton « Mises à jour ». Vérification discrète au démarrage, téléchargement, contrôle SHA-256, remplacement et redémarrage lors d'une nouvelle version GitHub. Confirmation obligatoire avant le téléchargement.
- **Catalogue épuré** : les entrées techniques sans nom d'objet sont masquées, tout comme les identifiants dans les infobulles et les fiches. La mention de bas de fiche a été supprimée.
- **Signature** « Made by Sami », numéro de version en bleu et bandeau illustré du jeu.

**Aucune connexion aux API d'Albion Online.** Aucun module de prix, de Black Market, de stockage boursier ou d'achat/vente n'est présent. Les données du catalogue restent entièrement locales. Seule la recherche d'une nouvelle version utilise Internet et l'API publique des *GitHub Releases* du dépôt `SamiLynair/Sami-Albion-Manager`.

## Mise à jour directement dans l'application

Une fois la **première version avec mise à jour intégrée** installée :

1. Lance « Sami Albion Manager.exe » : une vérification de version se fait en arrière-plan.
2. Si une nouvelle version est disponible, accepte ou refuse la proposition. Tu peux aussi cliquer sur la roue crantée, puis sur « Mises à jour » dans les Paramètres.
3. Le téléchargement se fait dans un dossier temporaire. Le programme contrôle le SHA-256 publié par GitHub avant toute installation.
4. Une copie du logiciel agit comme utilitaire de mise à jour : elle attend la fermeture de l'ancien programme, sauvegarde l'ancien exécutable, le remplace puis lance le nouveau.

**À mettre en place une seule fois** : il faut d'abord publier sur GitHub une Release contenant l'exécutable Windows nommé `Sami-Albion-Manager-Windows.exe`. Tant que le dépôt n'a aucune Release, le bouton indique simplement qu'aucune mise à jour n'est disponible. L'installation automatisée ne fonctionne pas dans les sources Python, seulement dans l'exécutable Windows compilé.

Le fichier `.github/workflows/windows-release.yml` compile cet exécutable sur un runner Windows et publie une Release lorsqu'un tag Git correspondant à la version est créé (exemple : `v0.3.3`).

## Installation / compilation Windows 11

1. Télécharge l'archive du projet, puis fais **Extraire tout** dans un dossier neuf.
2. Ouvre `sami-albion-manager`.
3. Installe Python depuis <https://www.python.org/downloads/windows/> si nécessaire, en cochant « Add Python to PATH ».
4. Double-clique sur `build_windows.bat`. Il installe Qt/PyInstaller et compile le `.exe` autonome avec les icônes déjà incluses.
5. Lance `dist\Sami Albion Manager.exe`.

L'archive fournit le **projet complet** et le compilateur automatique ; le `.exe` Windows n'est pas compilé directement sous Linux. Les images augmentent le volume de l'exécutable et le temps de compilation.

## Contrôle des données

Le catalogue est un instantané local, pas une synchronisation du jeu en temps réel : les nouveaux objets ajoutés par un patch devront faire l'objet d'une mise à jour. Les enchantements et les qualités n'existent pas sur tous les objets ; le filtre de qualité s'applique aux équipements reconnus.

Les images sont propriété de leurs ayants droit dans Albion Online. Le service officiel de rendu des objets a uniquement servi à **préparer le pack d'images** ; l'exécutable ne télécharge aucune image d'objet pendant son utilisation. Le script de développement `tools/build_item_icons.py` (non inclus dans le logiciel livré) permet de reconstituer ce pack.

Tes anciens stocks des premières versions, enregistrés sous `%APPDATA%\SamiAlbionManager\manager.db`, ne sont ni lus ni modifiés.

Chaque nouvelle fonctionnalité finalisée et testée est publiée en version numérotée sur GitHub, conformément à la préférence de Sami.

## Vérification

```powershell
py -3 -m unittest discover -s tests -v
```
