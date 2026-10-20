# IPInsight CLI

> Analyse informative d'une adresse IP publique — géolocalisation approximative, réseau (FAI / ASN) et indicateurs d'anonymisation — pour la **cybersécurité défensive**, l'**administration réseau**, les **audits autorisés** et l'**apprentissage**.

**IPInsight CLI — Developed by Abiye Enzo (@abiyeenzo)** · Licence MIT · Python 3.11+

---

## Sommaire

1. [Fonctionnalités](#fonctionnalités)
2. [Installation](#installation) (Linux, macOS, Windows)
3. [Utilisation](#utilisation)
4. [Format JSON](#format-json)
5. [Confidentialité et requêtes externes](#confidentialité-et-requêtes-externes)
6. [Limites techniques](#limites-techniques)
7. [Tests](#tests)
8. [Structure du projet](#structure-du-projet)
9. [Usage responsable](#usage-responsable)

## Fonctionnalités

- Validation stricte IPv4 / IPv6 ; rejet des adresses mal formées ; détection des adresses **privées, loopback, link-local, multicast, réservées ou non routables** (aucune requête externe n'est faite pour elles).
- Géolocalisation : pays, région, ville, fuseau horaire, latitude/longitude **estimées**, FAI, organisation, ASN, domaine.
- Liens cartographiques (Google Maps et OpenStreetMap) générés **uniquement** si la source fournit des coordonnées valides. Option pour les ouvrir ou les copier.
- Indicateurs **indicatifs** de VPN, proxy, nœud de sortie Tor et hébergeur / centre de données.
- Mode `--self` : analyse de l'adresse IP publique de la machine.
- Sortie terminal (Rich, bannière, catégories, statuts ✔ / ⚠ / ✖) ou **JSON** structuré ; mode `--no-color`.
- Modes interactif et non interactif ; interruptions (Ctrl+C) et erreurs gérées proprement.
- Aucune télémétrie, aucun stockage des adresses analysées, aucune clé API requise.

Principes non négociables : une position IP **n'est jamais** présentée comme une position GPS ; les données absentes restent `null` (jamais inventées) ; l'absence d'indicateur VPN **ne prouve pas** l'absence de VPN.

## Installation

Prérequis : **Python 3.11 ou plus récent** et un accès HTTPS sortant.

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

> Si l'activation est bloquée par la politique d'exécution : `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`.
> Sur un terminal sans UTF-8, les symboles ✔ ⚠ ✖ sont remplacés automatiquement par `[OK]` `[!]` `[x]` ; `--no-color` supprime toute couleur.

## Utilisation

```text
python main.py --help                  # aide
python main.py --version               # version et signature
python main.py --ip 8.8.8.8            # analyse d'une adresse
python main.py --ip 2001:4860:4860::8888
python main.py --ip 8.8.8.8 --json     # sortie JSON (stdout = JSON uniquement)
python main.py --self                  # IP publique de cette machine
python main.py                         # mode interactif (terminal)
python main.py --disclaimer            # relire l'avertissement d'usage
```

| Option | Rôle |
|---|---|
| `--ip ADRESSE` | Adresse IPv4/IPv6 publique à analyser |
| `--self` | Analyser l'IP publique de la machine |
| `-i`, `--interactive` | Forcer le mode interactif (commandes : adresse, `self`, `disclaimer`, `help`, `quit`) |
| `--json` | Sortie JSON structurée |
| `--no-color` | Désactiver couleurs et styles (la variable `NO_COLOR` est aussi respectée) |
| `--no-anonymity` | Ne pas interroger les sources VPN/proxy/Tor (moins de requêtes externes) |
| `--rdns` | Ajouter un DNS inverse via **votre** résolveur système |
| `--open-map` / `--copy-map` | Ouvrir / copier le lien Google Maps |
| `--timeout S` | Délai d'attente réseau par requête (défaut 8 s) |
| `--disclaimer` | Afficher l'avertissement d'usage |

**Codes de sortie** : `0` succès · `1` erreur de source ou de réseau (aucun résultat inventé) · `2` entrée invalide · `3` adresse non publique (aucune requête) · `130` interruption.

L'avertissement d'usage s'affiche au **premier lancement** (sur `stderr`, pour garder `stdout` propre en JSON). Seul un fichier marqueur vide est créé dans le dossier de configuration (`~/.config/ipinsight-cli/` ou `%APPDATA%\ipinsight-cli\`) ; la variable `IPINSIGHT_CONFIG_DIR` permet de le changer.

### Lecture des indicateurs d'anonymisation

| Message | Signification |
|---|---|
| `VPN : probablement détecté` / `Proxy : probablement détecté` | Une source consultée signale l'adresse |
| `Tor : indicateur détecté` | Adresse présente dans la liste des nœuds de sortie Tor ou signalée |
| `Hébergement : indicateur détecté` | Adresse appartenant à un hébergeur / centre de données |
| `Aucun indicateur trouvé dans la source consultée` | **Ne prouve pas** l'absence de VPN |
| `Indéterminé : données insuffisantes` | Sources indisponibles ou réponses inexploitables |

L'outil ne cherche ni à contourner un VPN, ni à retrouver une adresse d'origine, ni à identifier une personne.

## Format JSON

```json
{
  "ip": "8.8.8.8",
  "ip_scope": "public",
  "country": "United States",
  "country_code": "US",
  "region": "California",
  "city": "Mountain View",
  "latitude": 37.386052,
  "longitude": -122.083851,
  "accuracy_radius_km": null,
  "timezone": "America/Los_Angeles",
  "isp": "Google LLC",
  "organization": "Google LLC",
  "asn": 15169,
  "domain": "google.com",
  "reverse_dns": null,
  "vpn_detected": null,
  "proxy_detected": null,
  "tor_detected": null,
  "hosting_detected": null,
  "anonymity_status": "no_indicator_found",
  "anonymity_errors": [],
  "maps_url": "https://www.google.com/maps?q=37.386052,-122.083851",
  "osm_url": "https://www.openstreetmap.org/?mlat=37.386052&mlon=-122.083851#map=10/37.386052/-122.083851",
  "source": { "geolocation": "ipwho.is", "anonymity": ["ipapi.is", "Tor Project (liste des nœuds de sortie)"] },
  "timestamp": "2026-10-20T22:00:00+00:00",
  "limitations": ["La géolocalisation IP est approximative : …"]
}
```

*(Exemple de structure — les valeurs réelles dépendent des sources au moment de l'appel.)*

- `*_detected` vaut `true` si un indicateur est signalé, sinon `null` : **jamais `false`**, car l'absence d'indicateur ne prouve rien. Voir `anonymity_status` : `indicators_found`, `no_indicator_found` ou `indeterminate`.
- `accuracy_radius_km` est `null` avec la source actuelle (elle ne fournit pas de rayon d'incertitude) : la précision est alors **inconnue**.
- En cas d'erreur : `{"ip": …, "error": "…", "error_type": "invalid_ip | network_unavailable | timeout | rate_limited | provider_error"}`.

## Confidentialité et requêtes externes

| Service | Quand | Donnée envoyée |
|---|---|---|
| `ipwho.is` | Toujours | L'adresse IP analysée (dans l'URL). Avec `--self`, le fournisseur voit l'IP source de votre connexion |
| `api.ipapi.is` | Sauf `--no-anonymity` | L'adresse IP analysée |
| `check.torproject.org` | Sauf `--no-anonymity` | Rien (téléchargement de la liste publique des nœuds de sortie) |
| Résolveur DNS système | Seulement avec `--rdns` | L'adresse IP analysée (requête PTR) |

L'outil n'envoie **rien** à un serveur de l'auteur, ne stocke **aucune** adresse analysée, ne contient aucune clé API, impose HTTPS avec validation TLS, limite le rythme des requêtes (≥ 0,5 s entre deux appels) et n'exécute aucune commande construite à partir d'une entrée utilisateur. Détails : [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## Limites techniques

- La géolocalisation IP est **approximative** (souvent au niveau de la ville, parfois du pays seulement) ; elle reflète l'infrastructure du fournisseur d'accès, pas la position d'une personne.
- Les sources gratuites peuvent changer, imposer des quotas ou devenir indisponibles : l'outil affiche alors une erreur explicite plutôt qu'un faux résultat.
- Les conditions d'utilisation et quotas des services tiers ne sont pas garantis par ce projet : **vérifiez-les avant tout usage professionnel ou à grande échelle** (voir `docs/DATA_SOURCES.md`).
- La détection VPN/proxy/hébergement dépend de la couverture des sources : faux négatifs et faux positifs sont possibles.
- Seules les adresses publiques sont analysées ; pas d'analyse de lots, pas de scan de ports.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Les tests n'effectuent **aucune requête réseau réelle** : toutes les réponses des fournisseurs sont simulées (réponses complètes ou incomplètes, délais d'attente, absence de connexion, quotas, JSON invalide, indicateurs indisponibles).

## Structure du projet

```text
ipinsight-cli/
├── main.py                  # point d'entrée
├── requirements.txt / requirements-dev.txt
├── src/
│   ├── cli.py               # arguments, modes interactif / non interactif, codes de sortie
│   ├── analysis.py          # orchestration d'une analyse
│   ├── validation.py        # validation et classification des IP
│   ├── geolocation.py       # source de géolocalisation (ipwho.is)
│   ├── network_info.py      # DNS inverse optionnel
│   ├── anonymity_check.py   # indicateurs VPN / proxy / Tor / hébergement
│   ├── maps.py              # liens cartographiques, ouverture, presse-papiers
│   ├── output.py            # rendu terminal (Rich) et JSON
│   ├── disclaimer.py        # avertissement d'usage
│   ├── http_client.py       # client HTTPS (stdlib), erreurs explicites
│   └── models.py            # modèles de données
├── tests/
├── docs/                    # DATA_SOURCES.md, LEGAL_AND_ETHICAL_USE.md
├── LICENSE · CONTRIBUTING.md · CHANGELOG.md
```

## Usage responsable

Utilisez IPInsight CLI uniquement pour l'apprentissage, l'administration de réseaux dont vous êtes responsable, le diagnostic, les audits autorisés et l'analyse défensive. Voir [`docs/LEGAL_AND_ETHICAL_USE.md`](docs/LEGAL_AND_ETHICAL_USE.md).

---

© 2026 Abiye Enzo — GitHub [@abiyeenzo](https://github.com/abiyeenzo) · Licence MIT
