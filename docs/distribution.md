# Distribution

## Wheel

```bash
python -m pip wheel . --no-deps --wheel-dir dist
```
Le wheel installe `call-of-python` et les ressources dans
`share/call-of-python/assets`. `resources.py` resout les chemins en mode
source, installation et PyInstaller.

## Executable autonome

```bash
python -m pip install ".[build]"
python -m PyInstaller --clean --noconfirm call_of_python.spec
```

Le resultat est dans `dist/Call-Of-Python/`. Le workflow `Executables`, lance
sur un tag `v*` ou manuellement, produit les variantes Windows et Linux. Les
builds sont natifs et ne sont pas reutilisables sur un autre OS.

## Validation

```bash
ruff check .
python -m coverage run -m unittest discover -s tests -v
python -m coverage report
python -m pip wheel . --no-deps --wheel-dir dist
```

La version gameplay 0.5.0 inclut les nouveaux modules dans le wheel. Pour
valider la résolution des ressources, installer le wheel dans un environnement
virtuel puis lancer le jeu depuis un autre répertoire. La recette automatisée
complète les tests, sous SDL dummy en CI Windows et Ubuntu :

```bash
python tools/validate_gameplay.py --stage 10 --output gameplay-qa
```

Les builds natifs de cette version restent à produire via le workflow de release.

Le groupe de concurrence global est `executables-${{ github.ref }}`. Ne pas
y utiliser `matrix.os` : la matrice est disponible uniquement au niveau des
jobs. Ce défaut préexistant a été découvert et corrigé pendant la validation
distante de la PR gameplay ; les deux builds OS ne s’annulent pas mutuellement.
