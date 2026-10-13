# Revue du matin — banc d'essai Mistral

Ce dépôt reprend chaque matin le script de la [Revue du matin](https://github.com/martinparnin-svg/revue-du-matin)
et le fait lire par la voix de Mistral (Voxtral TTS), avec les mêmes jingles. Il ne modifie rien dans le dépôt principal.

- Flux podcast : https://martinparnin-svg.github.io/revue-du-matin-mistral/feed.xml
- Écoute des voix : https://martinparnin-svg.github.io/revue-du-matin-mistral/samples/

## Fonctionnement

1. Le workflow « Fabriquer l'épisode (Mistral) » passe trois fois chaque matin de semaine.
2. Il récupère `episodes/AAAA-MM-JJ.json` dans le dépôt principal (`scripts/sync_episode.py`).
3. Il fabrique le MP3 avec la voix réglée dans `config.yml` (`voice.mistral.voice_id`) et met à jour le flux.

Secret requis : `MISTRAL_API_KEY` (Settings › Secrets and variables › Actions).
