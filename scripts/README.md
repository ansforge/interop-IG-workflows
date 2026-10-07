# Scripts

Ce dossier regroupe l'ensemble des scripts utilitaires utilisés par l'action GitHub (`action.yml`) et par le `Dockerfile` de l'image `fhir-ig-builder`. Si vous déplacez ou renommez un fichier ici, pensez à mettre à jour les chemins correspondants dans `action.yml` et/ou `Dockerfile` (indiqués ci-dessous pour chaque script).

## `generate-warmup-config.mjs`

Génère un `sushi-config.yaml` de warmup à partir de `fhir-packages.txt` (liste des packages FHIR à précharger dans l'image Docker). Pour un package listé plusieurs fois avec des versions différentes, seule la dernière version rencontrée dans le fichier est conservée.

- **Entrées** : `<fichier fhir-packages.txt> <fichier sushi-config.yaml de sortie>`
- **Sortie** : un `sushi-config.yaml` minimal avec les dépendances FHIR correspondantes
- **Appelé par** :
  - `Dockerfile` (étape de warmup, génère `synthetic-ig/sushi-config.yaml`)
  - `.github/workflows/build-docker.yml` (calcule la liste de packages `PACKAGES_LIST` injectée dans le label OCI de l'image)

## `synthetic-ig/`

Fixture d'IG minimale (`ig.ini`, `sushi-config.yaml` placeholder, `input/pagecontent/index.md`, `input/fsh/`) utilisée uniquement au moment du **build de l'image Docker**. Le `Dockerfile` lance un build SUSHI + IG Publisher "à blanc" sur cette IG synthétique (dont le `sushi-config.yaml` est régénéré par `generate-warmup-config.mjs` avec les packages de `fhir-packages.txt`), afin de précharger et valider le cache de packages FHIR (`~/.fhir/packages/`) directement dans l'image.

- **Appelé par** : `Dockerfile` (étape de warmup)

## `generate-branch-index.py`

Interroge l'API GitHub REST pour générer la page de listing des branches publiées sur `gh-pages` (affichée à la racine du site ci-build, `https://ansforge.github.io/{repo}/`) : branche par défaut du repo en tête, autres branches triées par date de dernière mise à jour décroissante (dates affichées en heure de Paris, `zoneinfo`). Détecte récursivement les dossiers de branches (marqueur : présence d'un sous-dossier `ig/`), pour gérer les noms de branches contenant des "/" (ex. `feat/ma-feature`). Ne fait jamais échouer le build : en cas d'erreur de l'API GitHub (rate limit, 5xx, réseau), se rabat sur une page limitée à la branche en cours de build. Si une `canonical_url` est fournie, affiche un bandeau rappelant qu'il s'agit de previews d'intégration continue et pointant vers l'IG officiellement publié.

Requiert Python 3 (stdlib uniquement) et la variable d'environnement `GITHUB_TOKEN`.

- **Entrées** : `<owner/repo> <branche en cours de build> <chemin du fichier .html de sortie> [<canonical_url>]` — `canonical_url` est optionnelle (le bandeau est simplement omis si absente/vide)
- **Appelé par** : `action.yml`, étape "Generate site root listing page", quand l'input `github_page: true` (passe la `canonical` lue dans `sushi-config.yaml` du repo IG)

## `plantuml/`

Scripts Python qui interrogent la base sqlite `package.db` (générée par l'IG Publisher dans `output/`) pour produire des diagrammes PlantUML **additionnels** montrant les liens entre les artefacts FHIR d'un IG. Ces diagrammes ne remplacent pas la génération native de diagrammes PlantUML de l'IG Publisher (voir la [documentation HL7](https://build.fhir.org/ig/FHIR/ig-guidance/diagrams-plantuml.html)).

Requièrent Python 3 (aucune dépendance externe, uniquement `sqlite3`/`json`/stdlib).

### `plantuml/construct.py`

Génère `graph.puml` : un diagramme des StructureDefinitions de l'IG (héritage, éléments, cardinalités, ValueSets, mappings).

- **Entrées** : `<chemin vers package.db> <chemin du fichier .puml de sortie>`
- **Appelé par** : `action.yml`, étape "🎨 Run PlantUML (parallel)", quand l'input `generate_plantuml: true`

### `plantuml/construct_mapping_global.py`

Génère, dans le dossier de sortie, un diagramme de mapping global entre les profils de l'IG.

- **Entrées** : `<chemin vers package.db> <dossier de sortie>`
- **Appelé par** : `action.yml`, même étape, quand l'input `generate_mapping_plantuml: true`

### `plantuml/construct_mappings.py`

Génère, dans le même dossier de sortie, un diagramme de mapping détaillé par ressource.

- **Entrées** : `<chemin vers package.db> <dossier de sortie>`
- **Appelé par** : `action.yml`, même étape, quand l'input `generate_mapping_plantuml: true`
