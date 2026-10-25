# IPInsight CLI

> Analyse informative d'une adresse IP publique : géolocalisation approximative comparée entre plusieurs sources, réseau (FAI / ASN) et indicateurs d'anonymisation. Pour la **cybersécurité défensive**, l'**administration réseau**, les **audits autorisés** et l'**apprentissage**.

**IPInsight CLI - Developed by Abiye Enzo (@abiyeenzo)** · Licence MIT · Python 3.11+ · v1.2.0

---

## Sommaire

1. [Fonctionnalités](#fonctionnalités)
2. [Installation](#installation) (Linux, macOS, Windows)
3. [Utilisation](#utilisation)
4. [Fiabilité de la géolocalisation](#fiabilité-de-la-géolocalisation)
5. [Mode hors ligne et bases locales](#mode-hors-ligne-et-bases-locales)
6. [Format JSON](#format-json)
7. [Confidentialité et requêtes externes](#confidentialité-et-requêtes-externes)
8. [Limites techniques](#limites-techniques)
9. [Tests](#tests)
10. [Structure du projet](#structure-du-projet)
11. [Usage responsable](#usage-responsable)

## Fonctionnalités

- Validation stricte IPv4 / IPv6 ; adresses **privées, loopback, link-local, multicast, réservées ou non routables** reconnues (aucune requête externe pour elles).
- **Plusieurs sources comparées** : ipwho.is, ipapi.is et bases locales `.mmdb` (DB-IP Lite, GeoLite2...). Chaque résultat indique sa source, la date de sa base (si connue) et son rayon d'incertitude (si fourni).
- **Divergences affichées** : distance entre sources, accord sur le pays, niveau de confiance qualitatif **avec son explication**. Les bases de même famille ne sont jamais comptées comme confirmations indépendantes.
- **Sources contradictoires** : aucune position n'est choisie, chaque estimation est affichée séparément.
- **Validation des coordonnées** : valeurs invalides, absentes, inversion latitude/longitude, point (0, 0). Rien n'est corrigé silencieusement.
- Liens **Google Maps** et **OpenStreetMap** construits à partir des mêmes valeurs et du même zoom (voir [le diagnostic](docs/GEOLOCATION_METHOD.md)).
- **Géocodage inverse facultatif** (Nominatim) : contexte autour du point estimé, sans quartier ni rue déduits d'une estimation de ville.
- **Consultation RDAP facultative** (`--rdap`, RFC 9083) : préfixe CIDR, plage IP, titulaire déclaré et contact d'abus auprès des registres Internet régionaux (ARIN, RIPE NCC, APNIC, LACNIC, AFRINIC).
- **Mode hors ligne** avec vos bases locales ; lecteur `.mmdb` intégré, sans dépendance.
- Indicateurs **indicatifs** de VPN, proxy, nœud de sortie Tor et hébergeur ; rappel permanent que la position peut être celle d'un serveur intermédiaire.
- Mode `--self`, sortie terminal (Rich) ou **JSON**, export direct vers fichier (`-o` / `--output`), `--no-color`, mode interactif, exécutable autonome Windows (`ipinsight.exe`).
- Aucune télémétrie, aucun stockage des adresses analysées, aucune clé API obligatoire.

Principes non négociables : une position IP **n'est jamais** présentée comme une position GPS ; les données absentes restent `null` ; l'absence d'indicateur VPN **ne prouve pas** l'absence de VPN ; une adresse IP **ne permet pas** de suivre un appareil en temps réel.

## Installation

Prérequis : **Python 3.11 ou plus récent** et un accès HTTPS sortant (inutile en mode hors ligne).

### Linux

```bash
git clone https://github.com/abiyeenzo/ipinsight-cli.git   # ou décompressez IPInsight-CLI.zip
cd ipinsight-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --help
```

### macOS

```bash
cd ipinsight-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --help
```

### Windows (PowerShell)

```powershell
cd ipinsight-cli
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py --help
```

> Si l'activation est bloquée : `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`.
> Sans UTF-8, les symboles sont remplacés par `[OK]` `[!]` `[x]` ; `--no-color` supprime les couleurs.

### Exécutable autonome Windows (`ipinsight.exe`)

Un binaire autonome `ipinsight.exe` (sans installation de Python requise sur le poste cible) est compilé automatiquement par le workflow GitHub Actions (`.github/workflows/build-exe.yml`) à chaque push sur `main` ou lors d'une release. Vous pouvez aussi le générer localement sous Windows :

```powershell
pip install -r requirements.txt "pyinstaller>=6.0"
pyinstaller --clean --noconfirm ipinsight.spec
.\dist\ipinsight.exe --help
```

## Utilisation

```text
python main.py --help
python main.py --version
python main.py --ip 8.8.8.8
python main.py --ip 2001:4860:4860::8888
python main.py --ip 8.8.8.8 --json
python main.py --ip 8.8.8.8 --rdap --rdns -o rapport.json        # RDAP + DNS inverse + export fichier
python main.py --self
python main.py --ip 8.8.8.8 --mmdb dbip-city-lite.mmdb          # compare avec une base locale
python main.py --ip 8.8.8.8 --mmdb a.mmdb --mmdb b.mmdb          # plusieurs bases
python main.py --ip 8.8.8.8 --offline --mmdb dbip-city-lite.mmdb # aucune requête réseau
python main.py --ip 8.8.8.8 --reverse-geocode                    # contexte autour du point (Nominatim)
python main.py                                                   # mode interactif
python main.py --disclaimer                                      # avertissement d'usage
```

| Option | Rôle |
|---|---|
| `--ip ADRESSE` | Adresse IPv4/IPv6 publique à analyser |
| `--self` | Analyser l'IP publique de la machine (incompatible avec `--offline`) |
| `-i`, `--interactive` | Mode interactif (adresse, `self`, `disclaimer`, `help`, `quit`) |
| `--json` | Sortie JSON structurée (stdout = JSON uniquement) |
| `-o`, `--output FICHIER` | Enregistrer le rapport dans un fichier (`.json` en JSON, sinon texte UTF-8) |
| `--mmdb FICHIER` | Base locale `.mmdb`, répétable ; variable `IPINSIGHT_MMDB` acceptée |
| `--offline` | Aucune requête réseau ; nécessite au moins un `--mmdb` valide |
| `--reverse-geocode` | Géocodage inverse facultatif (envoie les **coordonnées estimées** à Nominatim) |
| `--rdap` | Enregistrement officiel RDAP auprès des registres RIR (CIDR, titulaire, contact abus) |
| `--no-anonymity` | Ne pas interroger les sources VPN/proxy/Tor |
| `--rdns` | DNS inverse via **votre** résolveur système |
| `--open-map` / `--copy-map` | Ouvrir / copier le lien Google Maps |
| `--no-color` | Désactiver couleurs et styles |
| `--timeout S` | Délai réseau par requête (défaut 8 s) |
| `--disclaimer` / `--version` | Avertissement d'usage / version |

Variable facultative : `IPINSIGHT_IPAPI_KEY` (clé gratuite ipapi.is, voir ci-dessous).

**Codes de sortie** : `0` succès · `1` erreur de source ou de réseau (aucun résultat inventé) · `2` entrée invalide ou option incompatible · `3` adresse non publique · `130` interruption.

L'avertissement d'usage s'affiche au **premier lancement** (sur `stderr`). Seul un fichier marqueur vide est créé dans `~/.config/ipinsight-cli/` ou `%APPDATA%\ipinsight-cli\` (`IPINSIGHT_CONFIG_DIR` pour changer).

### Indicateurs VPN, proxy, Tor, hébergeur

| Message | Signification |
|---|---|
| `VPN : probablement détecté` / `Proxy : probablement détecté` | Une source signale l'adresse |
| `Tor : indicateur détecté` | Nœud de sortie Tor connu |
| `Hébergement : indicateur détecté` | Adresse d'un hébergeur / centre de données |
| `Aucun indicateur trouvé dans la source consultée` | **Ne prouve pas** l'absence de VPN |
| `Indéterminé : données insuffisantes` | Sources indisponibles ou sans indicateurs |

**Important :** sans clé API, ipapi.is **ne renvoie pas** les indicateurs VPN/proxy/hébergeur (vérifié dans sa documentation). Sans clé, seule la liste Tor du Tor Project fonctionne et le reste est « Indéterminé ». Un compte gratuit donne une clé (1 000 requêtes/jour) : `export IPINSIGHT_IPAPI_KEY=...` (Windows : `$env:IPINSIGHT_IPAPI_KEY="..."`). La clé n'est jamais stockée ni affichée. Elle est facultative.

Si un indicateur est détecté, la confiance est plafonnée à « faible » : la position peut être celle d'un serveur intermédiaire. L'outil ne cherche ni à contourner un VPN ni à retrouver une adresse d'origine.

## Fiabilité de la géolocalisation

Détail complet : [`docs/GEOLOCATION_METHOD.md`](docs/GEOLOCATION_METHOD.md).

| Statut | Condition | Position retenue |
|---|---|---|
| `single_source` | une seule source | oui, confiance faible |
| `concordant` | écart ≤ 50 km, même pays | oui (point le plus central) |
| `divergent` | 50 à 300 km | oui, avec avertissement |
| `contradictory` | > 300 km ou pays différents | **aucune**, estimations séparées |
| `no_data` | aucune coordonnée valide | aucune |

Le **niveau de confiance** (aucune, faible, moyenne, plus élevée, non déterminable) est qualitatif, expliqué ligne par ligne, et **n'est pas une probabilité**. `moyenne` exige 2 familles de données indépendantes documentées qui concordent ; ipwho.is (origine non documentée) n'en compte jamais. Pour améliorer la vérification croisée, ajoutez une base locale (`--mmdb`).

**Corrections de la version 1.1.0 sur les cartes :** les deux liens utilisent les mêmes valeurs numériques et le même zoom ; les URL ne sont plus repliées par le terminal (à 80 colonnes, l'URL OpenStreetMap était tronquée et pointait à 75 m, à 60 colonnes elle perdait la longitude) ; les coordonnées s'affichent aussi sous la forme `lat,lon` à coller dans une carte.

## Mode hors ligne et bases locales

Aucune base n'est incluse (licences). Téléchargez la vôtre :

- **DB-IP Lite** (CC BY 4.0, attribution à DB-IP.com obligatoire, mensuelle, sans compte) : <https://db-ip.com/db/lite.php>
- **GeoLite2** (compte et clé MaxMind, EULA qui impose de la tenir à jour) : <https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/>

```bash
python main.py --ip 8.8.8.8 --offline --mmdb dbip-city-lite.mmdb
```

La date de construction de chaque base est affichée ; une base de plus de 120 jours est signalée. En mode hors ligne, l'anonymat n'est pas analysé et `--self` est refusé. Détails et licences : [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## Format JSON

Extrait de la structure (valeurs d'exemple) :

```json
{
  "ip": "8.8.8.8",
  "country": "France", "country_code": "FR", "region": "Ile-de-France", "city": "Paris",
  "latitude": 48.8566, "longitude": 2.3522, "accuracy_radius_km": null,
  "isp": "Exemple FAI", "asn": 64500,
  "vpn_detected": null, "proxy_detected": null, "tor_detected": null, "hosting_detected": null,
  "anonymity_status": "no_indicator_found",
  "maps_url": "https://www.google.com/maps?q=48.856600,2.352200&z=10",
  "osm_url": "https://www.openstreetmap.org/?mlat=48.856600&mlon=2.352200#map=10/48.856600/2.352200",
  "position_status": "concordant",
  "confidence": { "level": "medium", "label": "moyenne", "is_probability": false, "explanation": ["..."] },
  "comparison": { "status": "concordant", "max_divergence_km": 18.2, "independent_families": ["dbip", "ipapi.is"],
                  "position_selected_from": "base locale dbip-city-lite.mmdb", "pairs": [], "notes": [] },
  "estimates": [
    { "source": "ipwho.is", "kind": "online", "family": "unverified", "database_date": null,
      "latitude": 48.8566, "longitude": 2.3522, "accuracy_radius_km": null,
      "maps_url": "...", "osm_url": "...", "issues": [] }
  ],
  "reverse_geocode": null,
  "rdap": null,
  "source": { "geolocation": ["ipwho.is"], "position_selected_from": "ipwho.is", "network": {}, "anonymity": [] },
  "source_errors": [], "offline": false,
  "timestamp": "2026-10-21T08:00:00+00:00",
  "limitations": ["..."]
}
```

- `*_detected` vaut `true` ou `null`, **jamais `false`** (l'absence d'indicateur ne prouve rien).
- Si les sources se contredisent, `latitude`, `longitude`, `maps_url` et `city` sont `null` ; les estimations restent dans `estimates` avec leur propre lien.
- `accuracy_radius_km` n'est renseigné que si la source le fournit (GeoLite2) ; sinon `null`.
- Erreur : `{"ip": ..., "error": "...", "error_type": "invalid_ip | network_unavailable | timeout | rate_limited | provider_error | no_local_database"}`.

## Confidentialité et requêtes externes

| Service | Quand | Donnée envoyée |
|---|---|---|
| `ipwho.is` | sauf `--offline` | l'adresse IP analysée (avec `--self`, il voit l'IP source de votre connexion) |
| `api.ipapi.is` | sauf `--offline` | l'adresse IP analysée (une seule requête pour localisation et anonymat) |
| `check.torproject.org` | sauf `--offline` / `--no-anonymity` | rien (liste publique) |
| `nominatim.openstreetmap.org` | seulement `--reverse-geocode` | les coordonnées estimées |
| `rdap.org` (et RIR compétent) | seulement `--rdap` | l'adresse IP analysée |
| Résolveur DNS | seulement `--rdns` | l'adresse IP analysée |

Rien n'est envoyé à l'auteur, aucune adresse analysée n'est stockée, aucune clé n'est dans le code, HTTPS avec validation TLS, requêtes espacées, aucune commande système construite à partir d'une entrée utilisateur. Détails : [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## Limites techniques

- La géolocalisation IP est **approximative** (souvent la ville, parfois le pays seulement) et reflète l'infrastructure du fournisseur d'accès, pas la position d'une personne. **Aucune donnée n'est une vérité terrain.**
- Une adresse IP **ne permet pas** de suivre des déplacements en temps réel. La localisation GPS d'un appareil est un autre sujet, légitime seulement avec le consentement explicite de la personne : voir la section 8 de [`docs/GEOLOCATION_METHOD.md`](docs/GEOLOCATION_METHOD.md). L'outil n'en implémente aucune.
- Sans clé ipapi.is, les indicateurs VPN/proxy/hébergeur ne sont pas disponibles. Quota sans clé : 30 requêtes par adresse et par jour.
- Les seuils de comparaison (50 et 300 km) et les niveaux de confiance sont des heuristiques de prudence, **non calibrées statistiquement**.
- Haversine suppose une Terre sphérique (erreur jusqu'à environ 0,5 %).
- Les conditions des services tiers peuvent changer ; certaines (ipwho.is) n'ont pas pu être vérifiées. Voir `docs/DATA_SOURCES.md`.
- Je n'ai pas pu observer l'affichage réel de Google Maps et d'OpenStreetMap lors du développement : seules les valeurs numériques des URL sont vérifiées.
- Seules les adresses publiques sont analysées ; pas de lots, pas de scan de ports.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Les tests n'effectuent **aucune requête réseau réelle** : réponses des fournisseurs simulées, bases `.mmdb` de test fictives générées à la volée (`tests/mmdb_writer.py`).

## Structure du projet

```text
ipinsight-cli/
├── main.py
├── pyproject.toml · ipinsight.spec
├── requirements.txt / requirements-dev.txt
├── .github/workflows/       # tests CI multi-OS et génération de ipinsight.exe
├── src/
│   ├── cli.py               # arguments, modes, export fichier, codes de sortie
│   ├── analysis.py          # orchestration multi-sources
│   ├── validation.py        # validation et classification des IP
│   ├── geolocation.py       # ipwho.is et ipapi.is
│   ├── mmdb.py              # lecteur MaxMind DB en Python pur
│   ├── local_db.py          # bases locales, familles de données, dates
│   ├── coord_validation.py  # validation des coordonnées, inversions
│   ├── geo_math.py          # Haversine, distances, boîtes englobantes
│   ├── comparison.py        # comparaison des sources et confiance
│   ├── reverse_geocode.py   # géocodage inverse facultatif (Nominatim)
│   ├── rdap.py              # consultation RDAP facultative (registres RIR)
│   ├── maps.py              # liens cartographiques cohérents
│   ├── anonymity_check.py   # VPN / proxy / Tor / hébergement
│   ├── network_info.py      # DNS inverse optionnel
│   ├── output.py            # rendu terminal, export fichier et JSON
│   ├── disclaimer.py, http_client.py, models.py
├── tests/
├── docs/                    # DATA_SOURCES, GEOLOCATION_METHOD, LEGAL_AND_ETHICAL_USE
└── LICENSE · CONTRIBUTING.md · CHANGELOG.md
```

## Usage responsable

Utilisez IPInsight CLI uniquement pour l'apprentissage, l'administration de réseaux dont vous êtes responsable, le diagnostic, les audits autorisés et l'analyse défensive. Voir [`docs/LEGAL_AND_ETHICAL_USE.md`](docs/LEGAL_AND_ETHICAL_USE.md).

---

© 2026 Abiye Enzo, GitHub [@abiyeenzo](https://github.com/abiyeenzo) · Licence MIT
