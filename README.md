# EPG Archive

Système d'archivage long terme d'EPG (Electronic Program Guide) avec support multi-sources et fusion intelligente basée sur les priorités.

## Fonctionnalités

- **Archivage long terme** : Conserve les données EPG sur plusieurs mois/années
- **Multi-sources avec priorités** : Combine plusieurs sources XML avec un système de priorités
- **Fusion intelligente** : 
  - Détection de consensus entre sources (2/3 sources d'accord = priorité au consensus)
  - Priorité à la première source en cas de désaccord total
  - Enrichissement des données (description, catégorie, etc.) depuis toutes les sources
- **Mise à jour automatique** : Détecte et met à jour les changements dans les programmes déjà archivés
- **Tolérance temporelle** : Gère les petites différences de timing entre sources (configurable)

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
```

### Paramètres de configuration

- **archive_dir** : Répertoire où stocker les archives (par défaut : `./archive`)
- **time_tolerance_seconds** : Tolérance en secondes pour considérer deux programmes comme identiques (par défaut : 300 = 5 minutes)
- **sources** : Liste des sources EPG
  - **name** : Nom de la source
  - **url** : URL du fichier XML
  - **priority** : Priorité (1 = plus haute priorité)
  - **enabled** : Activer/désactiver la source

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

### Automatisation avec cron

Pour mettre à jour l'archive automatiquement, ajoutez une tâche cron :

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

Les archives sont exportées au **format XMLTV standard**, compatible avec tous les lecteurs EPG :

```
archive/
├── 2026-01-05.xml   # Fichier XMLTV du 5 janvier 2026
├── 2026-01-06.xml   # Fichier XMLTV du 6 janvier 2026
├── 2026-01-07.xml   # Fichier XMLTV du 7 janvier 2026
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

## Structure du projet

```
epg_archive/
├── __init__.py          # Package principal
├── models.py            # Modèles de données (Programme, Channel, EPGSource)
├── parser.py            # Parser XMLTV
├── fetcher.py           # Téléchargement concurrent des sources
├── merger.py            # Logique de fusion et consensus
├── exporter.py          # Export au format XMLTV
├── orchestrator.py      # Orchestration du processus complet
├── config.py            # Gestion de la configuration
├── console.py           # Interface console avec Rich (couleurs, tableaux)
├── utils.py             # Utilitaires partagés (parsing datetime)
└── cli.py               # Interface en ligne de commande
```

## Licence

MIT
