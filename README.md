![Logo_LEF_CI-SIS](https://user-images.githubusercontent.com/48218773/227532484-eff82649-4e42-49c6-966a-dc3ea78cf59c.png)

[![fr](https://img.shields.io/badge/lang-fr-blue.svg)](https://github.com/ansforge/IG-workflows/blob/main/README.md)
[![en](https://img.shields.io/badge/lang-en-red.svg)](https://github.com/ansforge/IG-workflows/blob/main/README.en.md)

# GitHub Action pour la publication d'IG FHIR

GitHub Action pour les IG FHIR : 
- [Lancement de sushi](#sushi)
- [Tests avec le validator_cli](#tests-avec-le-validator_cli)
- [Incorporation des projets de simplifier (méthode bake)](#incorporation-des-projets-de-simplifier)
- [Publication des releases sur un repo github](#génération-de-release-pour-publication)
- [Génération de diagrammes PlantUML additionnels illustrant les liens entre artefacts FHIR](#génération-du-diagramme-plantuml-de-lig) — ne remplace pas les diagrammes natifs de l'IG Publisher
- [Génération des diagrammes de mapping PlantUML additionnels](#génération-des-diagrammes-de-mapping-plantuml-de-lig)
- [Génération des testscripts avec le projet testscript-generator](#génération-des-fichiers-testscripts)
- [Optimisation des minutes GitHub Actions (annulation automatique des runs ci-build obsolètes)](#optimisation-des-minutes-github-actions-annulation-automatique-des-runs-ci-build-obsolètes)
- [Publication sur les pages github](#publication-sur-les-pages-de-github) :
  - IG
  - Diagramme de class plantuml généré à partir des données de l'IG
  - Rapport de validation du validator_cli

Pour tout ce qui concerne l'image Docker utilisée par cette action (contenu, versions, tags, politique de rétention), voir [DOCKER_IMAGE.md](./DOCKER_IMAGE.md).


## Usage

### Exemple Workflow file

Les exemples de workflows à jour (ci-build, release, nettoyage de gh-pages) ne sont plus dupliqués ici — ils sont maintenus dans le repo [ansforge/IG-modele](https://github.com/ansforge/IG-modele/tree/main/.github/workflows), utilisé comme modèle de référence pour tout nouveau repo IG :
- `fhir-workflows.yml` : ci-build (publication sur les pages GitHub à chaque push, avec le bloc `concurrency` décrit ci-dessous)
- `fhir-release.yml` : publication d'une release sur `ansforge/IG-website-release`
- `clean-gh-pages.yml` : nettoyage périodique des déploiements gh-pages de branches obsolètes

⚠️ Dans `fhir-release.yml`, `publish_path_outpout` dépend du volet de l'IG publiée et doit être adapté au repo, par exemple :
- `./IG-website-release/www/ig` — IG générique, à la racine
- `./IG-website-release/www/ig/fhir` — volet FHIR
- `./IG-website-release/www/ig/cda` — volet CDA
- `./IG-website-release/www/ig/hl7v2` — volet HL7v2

### Optimisation des minutes GitHub Actions (annulation automatique des runs ci-build obsolètes)

Quand plusieurs commits sont poussés rapidement sur une même branche, chaque push déclenche un run ci-build complet, même si le précédent run est déjà rendu obsolète. Le bloc `concurrency:` natif de GitHub Actions (déjà en place dans `fhir-workflows.yml` d'IG-modele) permet d'annuler automatiquement le run précédent dès qu'un nouveau démarre sur la même branche/PR, sans code custom :

```yaml
concurrency:
  group: ci-build-${{ github.workflow }}-${{ github.head_ref || github.ref }}
  cancel-in-progress: true
```

- `group` scope l'annulation par branche (et par PR via `head_ref`) : un push sur une branche n'annule jamais le run d'une autre branche.
- `github.workflow` dans la clé évite tout chevauchement avec le workflow de release, qui est un fichier séparé.
- **À réserver exclusivement au workflow ci-build.** Le workflow de release pousse vers `ansforge/IG-website-release` et crée une GitHub Release : l'annuler en cours de route peut laisser une publication à moitié faite. Ne jamais y ajouter `cancel-in-progress: true`.
- Le déploiement sur les pages GitHub (`gh-pages`) reste sûr à annuler côté ci-build : un `git push` est atomique par référence, et le run suivant republie de toute façon.
- Ce bloc doit être ajouté directement dans le fichier workflow de chaque repo consommateur (ci-build uniquement) — cette action composite ne peut pas l'imposer elle-même, puisque `concurrency:` est une propriété du fichier workflow appelant, pas de l'action.

### Inputs

| name | value | default | description |
|---|---|---|---|
| ig-publisher-version | string | latest | Version de l'IG Publisher : format `x.y.z` (ou `latest`) |
| github_page_token | string | | Token pour publier sur les GitHub Pages du repo |
| github_page | boolean | false | Publication de l'IG sur les GitHub Pages |
| generate_plantuml | boolean | false | Génération de diagrammes PlantUML **additionnels** montrant les liens entre les artefacts FHIR de l'IG (produits depuis `package.db`, publiés dans `gh-pages/plantuml`). Ne concerne **pas** la génération native des diagrammes PlantUML par l'IG Publisher — voir la [documentation HL7](https://build.fhir.org/ig/FHIR/ig-guidance/diagrams-plantuml.html) pour celle-ci |
| generate_mapping_plantuml | boolean | false | Génération de diagrammes PlantUML **additionnels** de mapping entre artefacts FHIR (publiés dans `gh-pages/plantuml_mapping`), même principe que `generate_plantuml` — ne remplace pas les diagrammes natifs de l'IG Publisher |
| generate_testscript | boolean | false | Génération des fichiers TestScripts à partir de l'IG |
| repo_ig | string | *(requis)* | Chemin d'accès au répertoire des sources de l'IG |
| bake | boolean | false | Permet d'inclure les projets annuaire et FrCore présents sur Simplifier (méthode bake) |
| validator_cli | boolean | false | Permet de lancer les tests avec le validator_cli d'HL7 |
| publish_repo | string | '' | Repo git de publication de l'IG (release) |
| publish_repo_token | string | '' | Token pour publier sur le repo git de publication |
| publish_path_outpout | string | '' | Chemin de publication de l'IG dans le repo de publication |
| container_mode | boolean | true | Le job tourne dans un container Docker (`container: image: ...`) : skip les installations d'outils (SUSHI, Java, Ruby… déjà présents dans l'image) |
| timing | boolean | false | Active le tableau de timings par phase (Setup, SUSHI, Publisher, Post-processing, Total) dans le résumé du workflow |


## Fonctionnalités

### Sushi

Principes :
- Installation de sushi
- Lancement de sushi
- Résultats accessibles via le terminal
  - ![image](https://github.com/ansforge/IG-workflows/assets/101335975/e8c0b772-b6a9-4006-be8e-403319996346)

### Incorporation des projets de simplifier
Pour installer les dépendances à des projets simplifier, il faut utiliser la méthode bake de simplifier : 
- Installation de .NET
- Installation du terminal firely
- Installation des projets :
  - ans.annuaire.fhir.r4
  - hl7.fhir.fr.core

### Tests avec le validator_cli

Principes : 
- Téléchargement de la dernière version du validator_cli
- Lancement des tests
- Affichage des résultats dans la sortie de l'action
- Publication des résultats dans les pages github (branch gh-pages)

### Génération du diagramme plantUML de l'IG

⚠️ Ces diagrammes sont **additionnels** : ils ne correspondent pas à la génération native des diagrammes PlantUML par l'IG Publisher (voir la [documentation HL7](https://build.fhir.org/ig/FHIR/ig-guidance/diagrams-plantuml.html) pour celle-ci). Ils sont produits par un script qui interroge la base sqlite `package.db` générée par le Publisher, pour visualiser les liens entre les différents artefacts FHIR de l'IG.

Principes : 
- Installation de python
- Lancement du script python de génération :
  - Requête sqlite sur la base de données sqlite générée par l'IG
  - Création du fichier plantuml
  - Génération du diagramme png et plantuml
- Publication des diagrammes dans les pages github (branch gh-pages)
  - ![image](https://github.com/ansforge/IG-workflows/assets/101335975/34ac663a-3c35-4da5-b7a1-883b20881eea)

### Génération des diagrammes de mapping plantUML de l'IG

⚠️ Même principe que la section précédente : diagrammes **additionnels** de mapping entre artefacts FHIR, distincts des diagrammes natifs de l'IG Publisher.

Principes : 
- Installation de python
- Lancement du script python de génération :
  - Requête sqlite sur la base de données sqlite générée par l'IG
  - Création des mappings
  - Génération du diagramme png et plantuml
- Publication des diagrammes dans les pages github (branch gh-pages)
  - ![image](https://github.com/ansforge/IG-workflows/assets/101335975/34ac663a-3c35-4da5-b7a1-883b20881eea)

### Génération des fichiers testscripts

Principes : 
- Installation du projet testscript-generator
- Lancement de la génération des testscripts :
  - bundle exec bin/testscript_generator read mustSupport search interaction 
- Publication des testscripts dans les pages github (branch gh-pages)
  - Les fichiers sont présents dans le sous-répertoire testscript dans la branche gh-pages

### Publication sur les pages de github 

Les éléments générés sont publiés sur les pages github (branch gh-pages) avec une sous-arborescence portant le nom de la branche :
 ![image](https://github.com/ansforge/IG-workflows/assets/101335975/660a6558-525b-4361-bbde-e74de4c1525d)

Les pages sont accessibles via : `https://ansforge.github.io/{nom du repo}/{nom de la branche}/ig/`

`https://ansforge.github.io/{nom du repo}/{nom de la branche}/` redirige automatiquement vers cette URL.

`https://ansforge.github.io/{nom du repo}/` affiche une page de listing de toutes les branches publiées (previews ci-build), avec la branche par défaut du repo en tête, et le reste trié par date de dernière mise à jour décroissante. Cette page est générée par `scripts/generate-branch-index.py`, qui interroge l'API GitHub pour lister les branches déjà publiées dans gh-pages.

### Génération de release pour publication
Principes : 
- Création de la version courante
- Création de la release pour publication
- Push de la release dans le repo distant
