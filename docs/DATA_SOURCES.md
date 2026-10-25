# Sources de données

IPInsight CLI n'embarque aucune base de données IP. Il interroge des services tiers gratuits et peut lire des bases locales fournies par l'utilisateur. Aucune clé payante n'est requise.

> **Vérification des conditions.** Les éléments marqués *(vérifié)* proviennent des pages officielles des fournisseurs consultées le 21 octobre 2026. Ceux marqués *(non vérifié)* n'ont pas pu être confirmés : consultez la page du fournisseur avant tout usage professionnel, commercial ou à volume élevé. Les conditions peuvent changer sans préavis.

## Récapitulatif des sources

| Source | Type | Famille | Mise à jour | Hors ligne | Clé | Rayon d'incertitude |
|---|---|---|---|---|---|---|
| ipwho.is | Service en ligne | non documentée | inconnue | non | non | non fourni |
| ipapi.is | Service en ligne | `ipapi.is` (base propre selon le fournisseur) | continue (non vérifié) | non | facultative | non fourni |
| Base locale DB-IP Lite (.mmdb) | Fichier local | `dbip` | mensuelle *(vérifié)* | **oui** | non | non fourni |
| Base locale GeoLite2 (.mmdb) | Fichier local | `maxmind` | voir ci-dessous | **oui** | compte + licence *(vérifié)* | oui (`accuracy_radius`) |
| Tor Project (liste des nœuds de sortie) | Liste publique | n/a | continue | non | non | n/a |
| Nominatim (géocodage inverse) | Service en ligne, facultatif | n/a | continue | non | non | n/a |
| RDAP (`rdap.org` / registres RIR) | Service en ligne, facultatif | n/a | continue | non | non | n/a |

## Requêtes externes et données envoyées

| Fournisseur | Quand | Donnée envoyée |
|---|---|---|
| `ipwho.is` | sauf `--offline` | l'adresse IP analysée ; avec `--self`, le fournisseur voit l'IP source de votre connexion |
| `api.ipapi.is` | sauf `--offline` | l'adresse IP analysée (et votre clé si vous en définissez une) ; **une seule requête** sert à la localisation et à l'anonymat |
| `check.torproject.org` | sauf `--offline` et `--no-anonymity` | rien (téléchargement de la liste publique) |
| `nominatim.openstreetmap.org` | seulement avec `--reverse-geocode` | les **coordonnées estimées** du point retenu (pas l'adresse IP) |
| `rdap.org` (et RIR compétent) | seulement avec `--rdap` | l'adresse IP analysée (requête HTTPS standard RFC 7480) |
| Résolveur DNS système | seulement avec `--rdns` | l'adresse IP analysée (requête PTR) |

Toutes les requêtes sont en HTTPS avec validation TLS, espacées, avec un `User-Agent` identifiant l'application. Rien n'est envoyé à l'auteur du projet et aucune adresse analysée n'est stockée.

## Détail par source

### ipapi.is *(vérifié)*
- Sans clé : **30 requêtes par adresse IP et par jour (UTC)**. Au-delà, des erreurs 429 puis un blocage de 24 h.
- **La réponse sans clé ne contient pas les indicateurs VPN / proxy / Tor / hébergement**, seulement la propriété et la localisation. Sans clé, l'outil le signale (« Indéterminé ») et s'appuie sur la liste Tor du Tor Project pour Tor.
- Compte gratuit avec clé : 1 000 requêtes par jour, usage commercial inclus selon le fournisseur. La clé est **facultative** : définissez la variable d'environnement `IPINSIGHT_IPAPI_KEY`. Elle n'est jamais écrite dans un fichier, jamais affichée, jamais incluse dans le JSON (testé).
- Les indicateurs VPN reposent sur la détection de nœuds de sortie ; les proxys résidentiels et mobiles ne sont pas détectés. Un résultat négatif ne prouve donc rien.

### ipwho.is
- Gratuit sans clé. Quotas et conditions précis **non vérifiés** : consultez le site du fournisseur.
- L'origine de ses données n'est pas documentée : la famille est `unverified`, donc jamais comptée comme confirmation indépendante.

### Bases locales .mmdb (hors ligne)
Passez-les avec `--mmdb FICHIER` (répétable) ou la variable `IPINSIGHT_MMDB` (séparateur `:` sous Linux/macOS, `;` sous Windows). L'outil lit le format MaxMind DB avec son propre lecteur en Python pur, sans dépendance.

**DB-IP Lite (« IP to City Lite ») *(vérifié)*** : licence Creative Commons Attribution 4.0 ; **l'attribution à DB-IP.com est obligatoire** (lien sur toute page web qui affiche les résultats) ; mise à jour mensuelle ; formats CSV et MMDB ; aucun compte n'est mentionné pour le téléchargement. Pas de rayon d'incertitude.

**GeoLite2 (MaxMind) *(vérifié)*** : compte MaxMind et clé de licence requis pour le téléchargement ; soumis au GeoLite End User License Agreement, qui impose de **tenir les données à jour** (suppression dans les 30 jours suivant une nouvelle version) ; 30 téléchargements par jour au maximum. Le champ `accuracy_radius` (rayon en km) est fourni par les bases City. Calendrier de publication non vérifié.

IPInsight CLI n'automatise pas le téléchargement et ne redistribue aucune base : respectez les licences ci-dessus. Il affiche la **date de construction** de chaque base et signale une base de plus de 120 jours.

### Nominatim (OpenStreetMap) *(vérifié)*
Politique : au maximum **1 requête par seconde** ; `User-Agent` identifiant l'application ; attribution « © OpenStreetMap contributors » (données ODbL) ; mise en cache des résultats ; requêtes systématiques ou en grille interdites ; ne pas soumettre de données personnelles ; l'application doit pouvoir être désactivée à la demande de l'OSMF. IPInsight CLI : option désactivée par défaut, 1,1 s minimum entre deux requêtes, cache en mémoire, une seule requête par analyse, attribution affichée. Le service public n'est pas prévu pour un usage intensif : pour du volume, installez votre propre instance.

### RDAP (`rdap.org` et registres Internet régionaux) *(vérifié)*
Le protocole RDAP (RFC 7480 / RFC 9083) est le successeur normalisé de WHOIS maintenu par l'IANA et les cinq registres régionaux (ARIN, RIPE NCC, APNIC, LACNIC, AFRINIC). Activé uniquement avec `--rdap` :
- Requête HTTPS vers `https://rdap.org/ip/<adresse>`, qui redirige vers le RIR compétent.
- Aucune clé requise ; mise en cache en mémoire pendant la session.
- Données extraites : bloc CIDR, plage d'adresses, nom et identifiant (`handle`) du réseau, registre RIR, titulaire déclaré, adresse e-mail de signalement d'abus (`abuse`), pays d'enregistrement administratif et dates d'allocation / mise à jour.
- Le pays RDAP désigne le siège administratif de l'organisation titulaire et non l'emplacement physique du routeur.

## Comportement en cas de problème

| Situation | Comportement |
|---|---|
| Pas de connexion | Erreur explicite (`network_unavailable`), code de sortie 1, aucun résultat inventé ; avec `--mmdb`, l'analyse locale reste possible |
| Une source en ligne échoue | Les autres sources sont utilisées ; l'échec est listé dans `source_errors` |
| Toutes les sources échouent | Erreur, aucun résultat |
| Délai dépassé / quota (HTTP 429) | Erreurs `timeout` / `rate_limited` |
| Réponse incomplète | Champs `null` ; coordonnées invalides écartées et signalées |
| Adresse absente de la base locale | Signalée, aucune estimation inventée |
| Base locale corrompue | Ignorée avec un avertissement |

## Licences des dépendances

| Composant | Licence |
|---|---|
| Rich | MIT |
| pytest (développement uniquement) | MIT |
| Bibliothèque standard Python (dont le lecteur MMDB écrit pour ce projet) | PSF / MIT |

IPInsight CLI est distribué sous licence MIT ; il n'embarque ni ne redistribue de données de géolocalisation.
