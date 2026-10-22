# Changelog

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ; versionnage sémantique.

## [1.1.0] - 2026-10-21

### Corrigé
- Cartes : les URL longues étaient repliées par le terminal (OpenStreetMap tronquée à 80 colonnes, longitude perdue à 60). Elles sont maintenant imprimées sur une ligne logique unique, et un test vérifie leur intégrité de 30 à 200 colonnes.
- Google Maps et OpenStreetMap utilisent désormais le même zoom (Google n'en avait aucun, ce qui donnait une impression de précision de rue).
- Anonymat : ipapi.is ne renvoie pas les indicateurs VPN/proxy/hébergeur sans clé ; le message l'explique et une clé gratuite facultative est acceptée (`IPINSIGHT_IPAPI_KEY`).

### Ajouté
- Sources multiples : ipapi.is et bases locales `.mmdb` (lecteur MaxMind DB en Python pur, mode `--offline`).
- Comparaison indépendante des sources : familles de données, écarts, pays, statuts, position retenue (jamais une moyenne fabriquée), confiance qualitative expliquée, jamais présentée comme une probabilité.
- Sources contradictoires : estimations affichées séparément, aucune position unique.
- Moteur de validation des coordonnées (absence, valeurs partielles, hors limites, virgule décimale, inversion lat/lon suspectée, point (0, 0)).
- Calculs géographiques (Haversine, distances, point central, boîte englobante).
- Géocodage inverse facultatif (Nominatim), quartier affiché seulement si la précision déclarée le justifie.
- Date des bases, signalement des bases anciennes, JSON enrichi (`estimates`, `comparison`, `confidence`, `source_errors`).
- Rappel permanent : la position peut être celle d'un serveur intermédiaire ; une IP ne permet pas le suivi en temps réel.
- Documentation : méthode de géolocalisation, licences et quotas vérifiés des sources.

### Modifié
- Suppression du caractère U+2014 (tiret cadratin) dans tout le projet, avec un test de non-régression.
- La signature est désormais `IPInsight CLI - Developed by Abiye Enzo (@abiyeenzo)`.

## [1.0.0] - 2026-10-20

### Ajouté
- Analyse d'une adresse IPv4/IPv6 publique (`--ip`) et de l'IP publique de la machine (`--self`).
- Validation stricte et classification (privée, loopback, link-local, multicast, réservée, non routable).
- Géolocalisation via ipwho.is : pays, région, ville, fuseau horaire, coordonnées estimées, FAI, organisation, ASN, domaine.
- Liens Google Maps et OpenStreetMap, ouverture et copie optionnelles.
- Indicateurs indicatifs VPN / proxy / Tor / hébergement (ipapi.is, liste des nœuds de sortie Tor).
- Sortie terminal (Rich) avec bannière et signature, sortie JSON, mode `--no-color`, mode interactif.
- Avertissement d'usage au premier lancement et option `--disclaimer`.
- Suite de tests automatisés sans requête réseau réelle.
- Documentation : README, sources de données, usage légal et éthique, guide de contribution.

Auteur : Abiye Enzo ([@abiyeenzo](https://github.com/abiyeenzo)).
