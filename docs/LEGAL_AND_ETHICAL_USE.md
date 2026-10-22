# Usage légal et éthique

> Cet outil est destiné à l'apprentissage, à l'administration réseau et aux analyses de cybersécurité autorisées. Avant toute analyse dans un contexte professionnel, assurez-vous de disposer des autorisations nécessaires et de respecter la législation applicable ainsi que les conditions d'utilisation des sources de données. La géolocalisation IP est approximative et ne permet pas de déterminer de manière fiable l'adresse exacte d'une personne.

(Affichable à tout moment avec `python main.py --disclaimer`.)

## Usages prévus

- Formation et apprentissage en cybersécurité.
- Administration de réseaux dont vous êtes responsable.
- Diagnostic réseau.
- Audit de sécurité autorisé.
- Analyse défensive d'indicateurs réseau (journaux, alertes).
- Étude de données IP en laboratoire.

## Usages exclus

Le projet n'a pas été conçu, et ne doit pas être détourné, pour :

- surveiller, localiser ou harceler une personne ;
- contourner un VPN, un proxy ou Tor, ou retrouver une adresse d'origine masquée ;
- collecter des données personnelles sans autorisation ;
- scanner des ports ou exploiter des systèmes (l'outil n'en a aucune capacité).

## Limites de la géolocalisation IP

Une adresse IP identifie un point d'un réseau, pas une personne. La position estimée correspond souvent à l'infrastructure du fournisseur d'accès, peut être éloignée de l'utilisateur réel, et n'a aucune valeur de preuve. Le lien cartographique affiche un point associé aux coordonnées estimées, **pas nécessairement la position physique de l'utilisateur**.

## Suivi et localisation GPS

Une adresse IP ne permet pas de suivre les déplacements d'une personne en temps réel. La localisation GPS d'un appareil exige le consentement explicite et éclairé de son utilisateur et les autorisations nécessaires ; elle n'est pas implémentée dans cet outil (voir `GEOLOCATION_METHOD.md`, section 8). Aucun suivi dissimulé n'est accepté dans le projet.

## Indicateurs VPN / proxy / Tor

Les résultats sont **indicatifs**. Une absence d'indicateur ne prouve pas l'absence d'anonymisation ; une détection peut être erronée.

## Responsabilité

L'utilisateur est seul responsable de l'usage qu'il fait de l'outil, du respect des lois applicables (protection des données, droit pénal informatique) et des conditions d'utilisation des services tiers. Le logiciel est fourni « tel quel » (licence MIT), sans garantie. Cette note n'est pas un avis juridique.
