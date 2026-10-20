# Changelog

Format inspiré de [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) ; versionnage sémantique.

## [1.0.0] — 2026-10-20

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
