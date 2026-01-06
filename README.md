# EPG Archive

Système d'archivage long terme d'EPG (Electronic Program Guide) avec support multi-sources et fusion intelligente basée sur les priorités.

## Fonctionnalités

- **Archivage long terme** : Conserve les données EPG sur plusieurs mois/années
- **Multi-sources avec priorités** : Combine plusieurs sources XMLTV et HTML avec un système de priorités
- **Scraping HTML** : Support des sites web sans flux XMLTV (ex: NouvelObs archives depuis 2024)
- **Fusion intelligente** : 
  - Détection de consensus entre sources (2/3 sources d'accord = priorité au consensus)
  - Priorité à la première source en cas de désaccord total
  - Enrichissement des données (description, catégorie, etc.) depuis toutes les sources
- **Mise à jour automatique** : Détecte et met à jour les changements dans les programmes déjà archivés
- **Tolérance temporelle** : Gère les petites différences de timing entre sources (configurable)
- **Organisation par année** : Archives organisées par dossiers annuels (archive/2024/, archive/2025/, etc.)

## Installation

### Prérequis

- Python 3.11 ou supérieur
- [uv](https://github.com/astral-sh/uv) (gestionnaire de paquets Python)

### Installation avec uv

```bash
# Cloner ou naviguer vers le projet
cd EPGArchive

# Créer l'environnement et installer les dépendances
uv sync

# Ou installer globalement
uv pip install -e .
```

## Configuration

### Créer le fichier de configuration

```bash
uv run epg-archive --init-config
```

Cela crée un fichier `config.yaml` avec la configuration par défaut :

```yaml
archive_dir: ./archive
time_tolerance_seconds: 300
sources:
  - name: EPG.pw
    url: https://epg.pw/xmltv/epg_FR.xml
    priority: 1
    enabled: true
  - name: XMLTV.fr
    url: https://xmltvfr.fr/xmltv/xmltv.xml
    priority: 2
    enabled: true

html_sources:
  - name: NouvelObs
    type: nouvelobs
    priority: 10
    enabled: true
    max_days_per_run: 30
```

### Paramètres de configuration

- **archive_dir** : Répertoire où stocker les archives (par défaut : `./archive`)
- **time_tolerance_seconds** : Tolérance en secondes pour considérer deux programmes comme identiques (par défaut : 300 = 5 minutes)
- **sources** : Liste des sources XMLTV
  - **name** : Nom de la source
  - **url** : URL du fichier XML
  - **priority** : Priorité (1 = plus haute priorité)
  - **enabled** : Activer/désactiver la source
- **html_sources** : Liste des sources HTML (scraping)
  - **name** : Nom de la source
  - **type** : Type de scraper (`nouvelobs`)
  - **priority** : Priorité (nombre plus élevé = priorité plus basse)
  - **enabled** : Activer/désactiver la source
  - **max_days_per_run** : Nombre maximum de jours à scraper par exécution (évite les timeouts)

### Ajouter des sources supplémentaires

Éditez `config.yaml` et ajoutez vos sources :

```yaml
sources:
  - name: Source1
    url: https://example.com/epg1.xml
    priority: 1
    enabled: true
  - name: Source2
    url: https://example.com/epg2.xml
    priority: 2
    enabled: true
  - name: Source3
    url: https://example.com/epg3.xml
    priority: 3
    enabled: true
```

## Utilisation

### Lancer une mise à jour de l'archive

```bash
uv run epg-archive
```

Avec un fichier de configuration personnalisé :

```bash
uv run epg-archive --config /path/to/config.yaml
```

Mode verbose pour plus de détails :

```bash
uv run epg-archive --verbose
```

### Voir les statistiques de l'archive

```bash
uv run epg-archive --stats
```

### Automatisation avec GitHub Actions

Le projet inclut un workflow GitHub Actions (`daily-update.yml`) qui :
- S'exécute automatiquement tous les jours à 6h UTC
- Récupère les EPG depuis toutes les sources configurées
- Commit et push les changements dans l'archive
- Déclenche le déploiement du viewer GitHub Pages

Pour l'activer, il suffit d'avoir le fichier `config.example.yaml` dans le repo.

### Automatisation avec cron (alternative locale)

Pour mettre à jour l'archive automatiquement en local, ajoutez une tâche cron :

```bash
# Éditer crontab
crontab -e

# Ajouter une ligne pour exécuter toutes les 6 heures
0 */6 * * * cd /path/to/EPGArchive && /path/to/uv run epg-archive >> /var/log/epg-archive.log 2>&1
```

## Fonctionnement

### Logique de fusion

Le système fusionne les données de plusieurs sources selon ces règles :

1. **Groupement** : Les programmes sont groupés par canal et créneau horaire exact
2. **Consensus** : Si 2+ sources sur 3 ont le même titre, ce titre est retenu
3. **Priorité** : En cas de désaccord total, la source avec la priorité la plus haute gagne
4. **Enrichissement** : Les champs manquants sont complétés depuis les autres sources

### Mise à jour des données

- Les programmes existants sont comparés avec les nouvelles données
- Si un programme a changé (titre, description, catégorie), il est mis à jour
- Les archives XML existantes sont fusionnées avec les nouvelles données

### Format d'export XMLTV

Les archives sont exportées au **format XMLTV standard**, organisées par année :

```
archive/
├── 2024/
│   ├── 2024-01-01.xml
│   ├── 2024-01-02.xml
│   └── ...
├── 2025/
│   ├── 2025-01-01.xml
│   └── ...
└── 2026/
    ├── 2026-01-05.xml
    ├── 2026-01-06.xml
    └── ...
```

**Chaque fichier XML contient :**
- Toutes les chaînes du jour avec leurs métadonnées
- Tous les programmes du jour, organisés par chaîne et heure
- Format 100% compatible avec les lecteurs EPG standards (Kodi, Plex, etc.)

**Exemple de structure :**
```xml
<?xml version='1.0' encoding='UTF-8'?>
<tv generator-info-name="EPG Archive">
  <channel id="TF1.fr">
    <display-name>TF1</display-name>
    <icon src="..."/>
  </channel>
  <programme channel="TF1.fr" start="20260106200000" stop="20260106210000">
    <title lang="fr">Journal de 20h</title>
    <desc lang="fr">L'actualité du jour</desc>
    <category lang="fr">Information</category>
  </programme>
  ...
</tv>
```

## Développement

### Installer les dépendances de développement

```bash
uv sync --dev
```

### Lancer les tests

```bash
uv run pytest
```

## Sources HTML (Scraping)

### NouvelObs Archive Scraper

Le scraper NouvelObs permet de récupérer les archives EPG depuis **programme-tv.nouvelobs.com** à partir du 1er janvier 2024.

**Fonctionnement :**
- Scrape automatiquement les jours manquants dans votre archive
- Parse 12 créneaux horaires par jour (0-2h, 2-4h, ..., 22-0h)
- Calcule automatiquement les durées réelles des programmes
- Affiche une barre de progression et un tableau récapitulatif

**Configuration :**
```yaml
html_sources:
  - name: NouvelObs
    type: nouvelobs
    priority: 10              # Priorité basse (sources XMLTV prioritaires)
    enabled: true
    max_days_per_run: 30      # Limite pour éviter les timeouts
```

**Exemple de sortie :**
```
📺 NouvelObs Archive Scraper
   Fetching 30 days: 2024-01-01 → 2024-01-30

  2024-01-30 (2,891 prog) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:02:15

  📺 NouvelObs Scrape Results  
╭────────────────┬────────────╮
│ Date           │ Programmes │
├────────────────┼────────────┤
│ 2024-01-01     │      2,811 │
│ 2024-01-02     │      2,913 │
│ ...            │        ... │
│ 2024-01-30     │      2,891 │
├────────────────┼────────────┤
│ Total (30 days)│     86,234 │
╰────────────────┴────────────╯
```

**Note :** Le scraper récupère progressivement l'historique. Avec `max_days_per_run: 30`, il faudra environ 25 exécutions pour récupérer 2 ans d'archives (730 jours).

## Viewer Web (GitHub Pages)

Le projet inclut un viewer web interactif déployé automatiquement sur GitHub Pages.

**Fonctionnalités du viewer :**
- Navigation par année et date
- Affichage des programmes par chaîne
- Recherche de programmes
- Interface responsive

**Déploiement automatique :**
Le workflow `pages.yml` déploie automatiquement le viewer après chaque mise à jour de l'archive.

## Structure du projet

```
epg_archive/
├── __init__.py              # Package principal
├── models.py                # Modèles de données (Programme, Channel, EPGSource)
├── parser.py                # Parser XMLTV
├── fetcher.py               # Téléchargement concurrent des sources
├── merger.py                # Logique de fusion et consensus
├── exporter.py              # Export au format XMLTV (organisé par année)
├── orchestrator.py          # Orchestration du processus complet
├── config.py                # Gestion de la configuration
├── console.py               # Interface console avec Rich (couleurs, tableaux)
├── utils.py                 # Utilitaires partagés (parsing datetime)
├── cli.py                   # Interface en ligne de commande
├── channel_normalizer.py    # Normalisation et fusion des chaînes dupliquées
├── overlap_detector.py      # Détection des chevauchements de programmes
└── scrapers/
    ├── __init__.py          # Module scrapers
    └── nouvelobs.py         # Scraper NouvelObs avec barre de progression

docs/
├── index.html           # Page principale du viewer
├── app.js               # Application JavaScript
├── styles.css           # Styles CSS
├── dates.json           # Index des dates disponibles (généré)
└── generate_index.py    # Script de génération de l'index
```

## Licence

MIT
