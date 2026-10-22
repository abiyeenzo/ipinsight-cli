# Méthode de géolocalisation et fiabilité

Ce document décrit ce que fait IPInsight CLI pour améliorer la fiabilité d'une estimation, et ce qu'il ne peut pas faire.

**Aucune donnée IP n'est une vérité terrain.** Toutes les positions sont des estimations produites par des tiers. IPInsight CLI distingue :

- **les données rapportées par une source** (pays, ville, coordonnées, rayon d'incertitude, date de la base) : elles sont affichées telles quelles, avec le nom de la source ;
- **les valeurs calculées par IPInsight CLI** (distances entre sources, position retenue, niveau de confiance) : elles servent à contrôler et à interpréter les données, jamais à produire une précision que les sources n'ont pas.

## 1. Diagnostic du problème des cartes

Constats vérifiés par tests automatisés (`tests/test_maps_consistency.py`) :

| Vérification | Résultat |
|---|---|
| Latitude et longitude inversées dans un lien | Non : latitude toujours en premier, testé sur 8 points dont les deux hémisphères |
| Limites WGS84 (lat ±90, lon ±180), degrés décimaux | Respectées ; hors limites, aucun lien n'est produit |
| Signes conservés, point décimal | Oui (ex. `-33.868800,-70.500000`) |
| Arrondi prématuré | Non : 6 décimales (environ 0,1 m), écart mesuré inférieur à 1 m |
| Mêmes valeurs dans Google Maps et OpenStreetMap | Oui : les deux URL sont construites à partir des mêmes chaînes `lat_text` / `lon_text` ; relues par `extract_coordinates`, elles donnent le même couple |
| Encodage des URL | Aucun caractère à encoder (chiffres, `-`, `.`, `,`) |
| Confusion avec une adresse ou un géocodage | Non : aucun géocodage dans la génération des liens ; `?q=lat,lon` est interprété comme des coordonnées |

**Cause réelle identifiée dans le code (corrigée) :** l'affichage terminal repliait les longues URL. Mesure avant correction, pour le point 37.386052, -122.083851 :

| Largeur du terminal | URL OpenStreetMap copiée depuis la première ligne | Écart avec le point exact |
|---|---|---|
| 120 colonnes | complète | 0 km |
| 100 colonnes | complète | 0 km |
| 80 colonnes | `...mlon=-122.083` (tronquée) | 0,075 km |
| 60 colonnes | `...mlat=37.` (longitude absente) | carte non fiable |
| 50 colonnes ou moins | aucune coordonnée | carte non fiable |

Un lien copié depuis un terminal étroit pouvait donc mener à un point différent, ou à une carte par défaut. Les URL sont maintenant imprimées sur une ligne logique unique (le terminal les replie visuellement sans insérer de saut de ligne), et un test vérifie leur intégrité de 30 à 200 colonnes.

**Cause probable des impressions de différence entre les deux cartes (données et affichage, pas le code) :**

1. Le lien Google précédent n'indiquait aucun zoom alors que celui d'OpenStreetMap forçait le zoom 10 : Google pouvait afficher une vue très rapprochée, donnant l'illusion d'une précision de rue. Les deux liens utilisent désormais le même zoom, adapté au rayon d'incertitude (ville si inconnu).
2. Les deux cartes ont des fonds, des libellés et un placement de repère différents.
3. Les sources placent souvent le point sur un centroïde de ville ou de zone, qui peut tomber dans un lieu sans rapport avec l'utilisateur.

*Limite de cette vérification :* l'environnement de développement n'a pas accès à Google Maps ni à OpenStreetMap ; l'affichage réel des cartes n'a pas été observé. Seules les valeurs numériques des URL ont été vérifiées.

## 2. Sources et indépendance

Les sources sont décrites dans [`DATA_SOURCES.md`](DATA_SOURCES.md). Chaque estimation porte une **famille de données** :

- `ipapi.is` : base propre du fournisseur selon sa documentation ;
- `dbip` / `maxmind` : déduites du type déclaré dans les métadonnées de la base locale (jamais du nom du fichier) ;
- `unverified` : origine des données non documentée (c'est le cas d'ipwho.is).

Règles :

- deux sources de la même famille comptent pour **une seule** (GeoLite2-City et GeoLite2-Country ne s'additionnent pas) ;
- une source d'origine non documentée n'est **jamais** comptée comme confirmation indépendante : une concordance entre elle et une autre source reste un indice, pas une preuve.

## 3. Comparaison et confiance

Seuils (heuristiques de prudence, **non calibrées statistiquement**) :

| Situation | Statut |
|---|---|
| Aucune coordonnée valide | `no_data` |
| Une seule source exploitable | `single_source` |
| Écart maximal de 50 km ou moins, même pays | `concordant` |
| Entre 50 et 300 km | `divergent` |
| Plus de 300 km, ou pays différents | `contradictory` : aucune position retenue, aucun lien principal, estimations affichées séparément |

Niveau de confiance (qualitatif, **jamais une probabilité**) :

| Niveau | Condition |
|---|---|
| aucune | aucune coordonnée |
| non déterminable | sources contradictoires |
| faible | source unique ; ou sources concordantes sans deux familles indépendantes documentées ; ou divergence notable |
| moyenne | 2 familles indépendantes concordantes |
| plus élevée (jamais certaine) | 3 familles indépendantes ou plus concordantes |

La confiance est plafonnée à « faible » si un indicateur VPN, proxy, Tor ou hébergeur est signalé : la position peut être celle d'un serveur intermédiaire. Chaque niveau est accompagné de son explication dans le terminal et dans le JSON (`confidence.explanation`, `confidence.is_probability: false`).

La position retenue est toujours l'une des estimations réelles (le point le plus central, au sens de la somme des distances), jamais une moyenne fabriquée. Avec deux sources seulement, le choix est arbitraire : les deux restent affichées.

## 4. Validation des coordonnées

`src/coord_validation.py` détecte et signale, sans jamais corriger silencieusement :

- coordonnées absentes ou partielles ;
- valeurs non numériques, NaN, booléens ;
- virgule décimale (refusée plutôt que devinée) ;
- hors limites WGS84 ;
- inversion latitude/longitude suspectée (valeur impossible comme latitude mais valide comme longitude, ou point permuté qui coïncide avec une autre source) ;
- point exact (0, 0), valeur de remplacement très probable ;
- code pays mal formé, rayon négatif, lieu sans coordonnées.

## 5. Calculs géographiques

`src/geo_math.py` : distance de Haversine (sphère de 6371,0088 km), inversion, distances par paires, point le plus central, boîte englobante (antiméridien géré), appartenance à un rayon.

**Limites de Haversine :** la Terre est supposée sphérique ; l'erreur peut atteindre environ 0,5 % par rapport à l'ellipsoïde WGS84. C'est négligeable pour comparer des estimations IP (dizaines à centaines de km), insuffisant pour de la géodésie de précision. Ces fonctions contrôlent des données existantes ; elles ne calculent pas la position réelle d'une personne.

## 6. Géocodage inverse (facultatif)

Option `--reverse-geocode`, désactivée par défaut, via Nominatim (OpenStreetMap). Niveau de détail limité à la ville (zoom 10). Un quartier n'est affiché que si le rayon d'incertitude fourni par la source est de 3 km ou moins **et** si Nominatim renvoie lui-même un quartier. Voir les contraintes d'usage dans [`DATA_SOURCES.md`](DATA_SOURCES.md).

## 7. Ce que l'outil ne fait pas

- Il ne suit pas les déplacements en temps réel : une adresse IP ne le permet pas.
- Il ne contourne pas un VPN, un proxy ou Tor et ne cherche pas l'adresse d'origine.
- Il ne déduit pas de quartier, de rue ou d'adresse à partir d'une estimation à l'échelle d'une ville.

## 8. Localisation GPS d'un appareil (hors périmètre de l'outil)

La localisation GPS d'un appareil est une autre technique, que cet outil n'implémente pas. Elle n'est légitime qu'avec le **consentement explicite et éclairé** de la personne concernée, et les autorisations nécessaires (par exemple dans un cadre professionnel déclaré). Voies légitimes :

- le partage de position natif des systèmes mobiles, activé par l'utilisateur, révocable à tout moment ;
- la géolocalisation du navigateur (API Geolocation du W3C), qui demande une permission explicite ;
- des solutions de gestion de flotte ou de parc d'appareils déclarées aux personnes concernées, dans le respect du droit applicable (information préalable, finalité, proportionnalité).

Aucun suivi dissimulé, aucune collecte clandestine et aucun contournement des protections de confidentialité ne seront ajoutés à IPInsight CLI.
