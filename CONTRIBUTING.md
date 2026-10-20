# Contribuer à IPInsight CLI

Merci de votre intérêt ! Projet créé par **Abiye Enzo** ([@abiyeenzo](https://github.com/abiyeenzo)), sous licence MIT.

## Mise en place

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest -q
```

## Règles

1. **Tests obligatoires** : toute modification de comportement s'accompagne de tests. Aucun test ne doit effectuer de requête réseau réelle (utilisez des fetchers simulés, voir `tests/conftest.py`).
2. **Code** : Python 3.11+, annotations de types, fonctions courtes, une responsabilité par module, pas de code mort.
3. **Garde-fous du projet (non négociables)** :
   - ne jamais présenter une position IP comme une position GPS exacte ;
   - ne jamais inventer une valeur manquante (utiliser `null`) ;
   - ne jamais affirmer qu'un VPN est absent faute d'indicateur ;
   - pas de télémétrie, pas de stockage des IP analysées, pas de clé API dans le code ;
   - HTTPS avec validation TLS toujours activée ;
   - pas de fonctionnalité de surveillance, de désanonymisation, de scan ou d'exploitation.
4. **Nouvelle source de données** : elle doit être gratuite, utilisable sans clé obligatoire, documentée dans `docs/DATA_SOURCES.md` (données envoyées, limites, conditions).
5. **Documentation** : mettez à jour `README.md` et `CHANGELOG.md`.

## Proposer une modification

Ouvrez une issue pour discuter, puis une pull request décrivant le changement et les tests ajoutés.

## Signaler un problème de sécurité

Ne publiez pas de détails sensibles dans une issue publique ; contactez l'auteur via son profil GitHub.
