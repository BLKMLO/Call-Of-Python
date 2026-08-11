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
