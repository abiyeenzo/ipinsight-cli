# Sources de données

IPInsight CLI n'embarque aucune base de données IP : il interroge des services tiers gratuits, sans clé API obligatoire. Chaque service est documenté ci-dessous.

> **À vérifier par l'utilisateur.** Les conditions d'utilisation, quotas et licences des services tiers peuvent changer. Au moment de la rédaction de ce projet, ils n'ont **pas pu être vérifiés de façon concluante** : consultez les pages officielles de chaque fournisseur avant un usage professionnel, commercial ou à volume élevé. Si un service ne convient plus, remplacez le module concerné (`src/geolocation.py` ou `src/anonymity_check.py`) — chaque fournisseur est isolé dans une seule fonction.

## Récapitulatif des requêtes

| Fournisseur | Module | URL interrogée | Donnée envoyée | Clé API |
|---|---|---|---|---|
| ipwho.is | `geolocation.py` | `https://ipwho.is/<ip>` (ou `https://ipwho.is/` avec `--self`) | L'adresse IP analysée ; avec `--self`, le fournisseur voit l'IP source de la connexion | Non |
| ipapi.is | `anonymity_check.py` | `https://api.ipapi.is/?q=<ip>` | L'adresse IP analysée | Non |
| Tor Project | `anonymity_check.py` | `https://check.torproject.org/torbulkexitlist` | Aucune (liste publique téléchargée, comparée localement) | Non |
| Résolveur DNS système | `network_info.py` | Requête PTR (option `--rdns`) | L'adresse IP analysée | Non |

Les requêtes sont toujours en HTTPS avec validation TLS, espacées d'au moins 0,5 seconde, avec un `User-Agent` `IPInsight-CLI/<version>`. Aucune donnée n'est envoyée à l'auteur du projet.

## Données exploitées

- **ipwho.is** : pays, code pays, région, ville, latitude, longitude, ASN, organisation, FAI, domaine, fuseau horaire. Le service ne fournit **pas** de rayon d'incertitude : `accuracy_radius_km` reste `null`.
- **ipapi.is** : uniquement les indicateurs `is_vpn`, `is_proxy`, `is_tor`, `is_datacenter`.
- **Liste Tor** : appartenance de l'adresse à l'ensemble des nœuds de sortie publiés.

## Comportement en cas de problème

| Situation | Comportement |
|---|---|
| Pas de connexion / DNS impossible | Erreur explicite (`network_unavailable`), code de sortie 1, aucun résultat affiché |
| Délai dépassé | Erreur `timeout` |
| Quota atteint (HTTP 429) | Erreur `rate_limited` |
| Réponse JSON invalide ou refusée | Erreur `provider_error` |
| Source d'anonymat indisponible | Le résultat de géolocalisation est affiché ; l'anonymat est « Indéterminé : données insuffisantes » |
| Champ absent de la réponse | `null` (terminal : « non disponible ») |

## Licences des dépendances

| Composant | Licence |
|---|---|
| Rich | MIT |
| pytest (développement uniquement) | MIT |
| Bibliothèque standard Python | PSF |

IPInsight CLI est distribué sous licence MIT ; il n'embarque ni ne redistribue de données de géolocalisation.
