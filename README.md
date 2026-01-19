# Système d'Extraction de Notes

Extraction automatisée de notes depuis des PDFs scannés vers Excel.

## Installation Rapide

```bash
cd grade_extraction
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Test

```bash
python main.py
```

Devrait afficher: "ALL IMPORTS WORKING!"

## Structure

- `core/` - Logique de traitement
- `models/` - Modèles de données
- `ui/` - Interface (à venir)
- `config.json` - Configuration

## Documentation

Voir INSTALL.md pour l'installation complète de Tesseract OCR.
