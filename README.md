# Revue du matin — banc d'essai Mistral

> **Banc d'essai terminé.** Depuis le 16 novembre 2026, le dépôt principal
> [revue-du-matin](https://github.com/martinparnin-svg/revue-du-matin) lit ses épisodes avec Voxtral
> (`voice.provider: mistral`) et sert de studio vocal unique (formats, créations hors flux, compétence
> Hermes). Le workflow de fabrication était déjà désactivé ; ses passages planifiés sont retirés pour
> qu'une réactivation ne fasse pas payer deux fois la même voix.
> Les outils d'essai (inventaire et extraits de voix, test de chapitre) restent lançables à la main.
> Ce dépôt peut être archivé (Settings › Archive this repository).

Ce dépôt reprend chaque matin le script de la [Revue du matin](https://github.com/martinparnin-svg/revue-du-matin)
et le fait lire par la voix de Mistral (Voxtral TTS), avec les mêmes jingles. Il ne modifie rien dans le dépôt principal.

- Flux podcast : https://martinparnin-svg.github.io/revue-du-matin-mistral/feed.xml
- Écoute des voix : https://martinparnin-svg.github.io/revue-du-matin-mistral/samples/

## Fonctionnement

1. Le workflow « Fabriquer l'épisode (Mistral) » passe trois fois chaque matin de semaine.
2. Il récupère `episodes/AAAA-MM-JJ.json` dans le dépôt principal (`scripts/sync_episode.py`).
3. Il fabrique le MP3 avec la voix réglée dans `config.yml` (`voice.mistral.voice_id`) et met à jour le flux.

Secret requis : `MISTRAL_API_KEY` (Settings › Secrets and variables › Actions).
