![Logo_LEF_CI-SIS](https://user-images.githubusercontent.com/48218773/227532484-eff82649-4e42-49c6-966a-dc3ea78cf59c.png)

[![fr](https://img.shields.io/badge/lang-fr-blue.svg)](https://github.com/ansforge/IG-workflows/blob/main/README.md)

# GitHub Action for FHIR IG publication

GitHub Action for FHIR IGs:
- [Running sushi](#sushi)
- [Tests with validator_cli](#tests-with-validator_cli)
- [Bundling Simplifier projects (bake method)](#bundling-simplifier-projects)
- [Publishing releases to a github repo](#generating-a-release-for-publication)
- [Generating additional PlantUML diagrams showing the links between FHIR artifacts](#generating-the-igs-plantuml-diagram) — does not replace the IG Publisher's native diagrams
- [Generating additional PlantUML mapping diagrams](#generating-plantuml-mapping-diagrams)
- [Generating testscripts with the testscript-generator project](#generating-testscript-files)
- [Optimizing GitHub Actions minutes (auto-cancelling stale ci-build runs)](#optimizing-github-actions-minutes-auto-cancelling-stale-ci-build-runs)
- [Publishing to github pages](#publishing-to-github-pages):
  - IG
  - Class diagram generated from the IG's data
  - validator_cli validation report

For everything related to the Docker image used by this action (contents, versions, tags, retention policy), see [DOCKER_IMAGE.md](./DOCKER_IMAGE.md) (French only).


## Usage

### Example Workflow File

Up-to-date workflow examples (ci-build, release, gh-pages cleanup) are not duplicated here — they are maintained in the [ansforge/IG-modele](https://github.com/ansforge/IG-modele/tree/main/.github/workflows) repo, used as the reference template for any new IG repo:
- `fhir-workflows.yml`: ci-build (publishes to GitHub Pages on every push, with the `concurrency` block described below)
- `fhir-release.yml`: publishes a release to `ansforge/IG-website-release`
- `clean-gh-pages.yml`: periodically cleans up stale branch deployments on gh-pages

⚠️ In `fhir-release.yml`, `publish_path_outpout` depends on the section of the published IG and must be adapted per repo, for example:
- `./IG-website-release/www/ig` — generic IG, at the root
- `./IG-website-release/www/ig/fhir` — FHIR section
- `./IG-website-release/www/ig/cda` — CDA section
- `./IG-website-release/www/ig/hl7v2` — HL7v2 section

### Optimizing GitHub Actions minutes (auto-cancelling stale ci-build runs)

When several commits are pushed in quick succession on the same branch, each push triggers a full ci-build run, even though the previous run is already made obsolete. GitHub Actions' native `concurrency:` block (already in place in IG-modele's `fhir-workflows.yml`) automatically cancels the previous run as soon as a new one starts on the same branch/PR, with no custom code:

```yaml
concurrency:
  group: ci-build-${{ github.workflow }}-${{ github.head_ref || github.ref }}
  cancel-in-progress: true
```

- `group` scopes cancellation per branch (and per PR via `head_ref`): a push on one branch never cancels another branch's run.
- `github.workflow` in the key prevents any overlap with the release workflow, which is a separate file.
- **Reserve this exclusively for the ci-build workflow.** The release workflow pushes to `ansforge/IG-website-release` and creates a GitHub Release: cancelling it mid-flight can leave a half-finished publication. Never add `cancel-in-progress: true` there.
- Cancelling the GitHub Pages deployment (`gh-pages`) mid-flight on the ci-build side is safe: a `git push` is atomic per ref, and the next run republishes anyway.
- This block must be added directly in each consumer repo's workflow file (ci-build only) — this composite action cannot enforce it itself, since `concurrency:` is a property of the calling workflow file, not of the action.

### Inputs

| name | value | default | description |
|---|---|---|---|
| ig-publisher-version | string | latest | IG Publisher version: format `x.y.z` (or `latest`) |
| github_page_token | string | | Token used to publish to the repo's GitHub Pages |
| github_page | boolean | false | Publish the IG to GitHub Pages |
| generate_plantuml | boolean | false | Generate **additional** PlantUML diagrams showing the links between the IG's FHIR artifacts (built from `package.db`, published to `gh-pages/plantuml`). Does **not** control the IG Publisher's native PlantUML diagram generation — see the [HL7 documentation](https://build.fhir.org/ig/FHIR/ig-guidance/diagrams-plantuml.html) for that |
| generate_mapping_plantuml | boolean | false | Generate **additional** PlantUML mapping diagrams between FHIR artifacts (published to `gh-pages/plantuml_mapping`), same principle as `generate_plantuml` — does not replace the IG Publisher's native diagrams |
| generate_testscript | boolean | false | Generate TestScript files from the IG |
| repo_ig | string | *(required)* | Path to the IG source directory |
| bake | boolean | false | Bundle the annuaire and FrCore projects hosted on Simplifier (bake method) |
| validator_cli | boolean | false | Run tests with HL7's validator_cli |
| publish_repo | string | '' | Git repo to publish the IG to (release) |
| publish_repo_token | string | '' | Token used to publish to the publication git repo |
| publish_path_outpout | string | '' | Publication path for the IG inside the publication repo |
| container_mode | boolean | true | The job runs inside a Docker container (`container: image: ...`): skips tool installation (SUSHI, Java, Ruby… already present in the image) |
| timing | boolean | false | Enables the per-phase timing table (Setup, SUSHI, Publisher, Post-processing, Total) in the workflow summary |


## Features

### Sushi

Principles:
- Install sushi
- Run sushi
- Results available in the terminal
  - ![image](https://github.com/ansforge/IG-workflows/assets/101335975/e8c0b772-b6a9-4006-be8e-403319996346)

### Bundling Simplifier projects
To install dependencies on Simplifier projects, the Simplifier bake method must be used:
- Install .NET
- Install the Firely terminal
- Install the projects:
  - ans.annuaire.fhir.r4
  - hl7.fhir.fr.core

### Tests with validator_cli

Principles:
- Download the latest version of validator_cli
- Run the tests
- Display results in the action's output
- Publish the results to github pages (gh-pages branch)

### Generating the IG's PlantUML diagram

⚠️ These diagrams are **additional**: they do not correspond to the IG Publisher's native PlantUML diagram generation (see the [HL7 documentation](https://build.fhir.org/ig/FHIR/ig-guidance/diagrams-plantuml.html) for that). They are produced by a script that queries the sqlite `package.db` generated by the Publisher, to visualize the links between the IG's various FHIR artifacts.

Principles:
- Install python
- Run the generation python script:
  - sqlite query on the sqlite database generated by the IG
  - Create the plantuml file
  - Generate the png and plantuml diagram
- Publish the diagrams to github pages (gh-pages branch)
  - ![image](https://github.com/ansforge/IG-workflows/assets/101335975/34ac663a-3c35-4da5-b7a1-883b20881eea)

### Generating PlantUML mapping diagrams

⚠️ Same principle as the previous section: **additional** mapping diagrams between FHIR artifacts, distinct from the IG Publisher's native diagrams.

Principles:
- Install python
- Run the generation python script:
  - sqlite query on the sqlite database generated by the IG
  - Create the mappings
  - Generate the png and plantuml diagram
- Publish the diagrams to github pages (gh-pages branch)
  - ![image](https://github.com/ansforge/IG-workflows/assets/101335975/34ac663a-3c35-4da5-b7a1-883b20881eea)

### Generating TestScript files

Principles:
- Install the testscript-generator project
- Run the testscript generation:
  - bundle exec bin/testscript_generator read mustSupport search interaction
- Publish the testscripts to github pages (gh-pages branch)
  - The files are available in the testscript subdirectory on the gh-pages branch

### Publishing to GitHub Pages

Generated artifacts are published to github pages (gh-pages branch) under a subdirectory named after the source branch:
 ![image](https://github.com/ansforge/IG-workflows/assets/101335975/660a6558-525b-4361-bbde-e74de4c1525d)

Pages are accessible at: `https://ansforge.github.io/{repo name}/{branch name}/ig/`

`https://ansforge.github.io/{repo name}/{branch name}/` automatically redirects to this URL.

`https://ansforge.github.io/{repo name}/` shows a listing page of all published branches (ci-build previews), with the repo's default branch first, and the rest sorted by last-updated date, most recent first. This page is generated by `scripts/generate-branch-index.py`, which queries the GitHub API to list the branches already published to gh-pages.

### Generating a release for publication
Principles:
- Create the current version
- Create the release for publication
- Push the release to the remote repo
