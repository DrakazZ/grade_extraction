#!/usr/bin/env python3
"""
Grade Extraction System - Project Generator
Run this script to create all project files automatically
"""

import os
from pathlib import Path

def create_file(path, content):
    """Create a file with given content"""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '\n')
    
    print(f"✓ Created: {path}")

def generate_project():
    """Generate complete project structure"""
    
    base_dir = Path("grade_extraction")
    base_dir.mkdir(exist_ok=True)
    
    print("=" * 70)
    print("GENERATING GRADE EXTRACTION PROJECT")
    print("=" * 70)
    print()
    
    # ========================================================================
    # 1. requirements.txt
    # ========================================================================
    create_file(base_dir / "requirements.txt", """
# PDF Processing
pdf2image==1.16.3
Pillow==10.1.0

# Computer Vision
opencv-python==4.8.1.78
numpy==1.24.3

# OCR
pytesseract==0.3.10
transformers==4.35.2
torch==2.1.0

# Excel Export
openpyxl==3.1.2
pandas==2.1.3

# UI
PyQt5==5.15.10

# Utilities
python-dotenv==1.0.0
""")
    
    # ========================================================================
    # 2. config.json
    # ========================================================================
    create_file(base_dir / "config.json", """{
  "ocr": {
    "tesseract_lang": "fra",
    "trocr_model": "microsoft/trocr-base-handwritten",
    "dpi": 300
  },
  "geometry": {
    "line_merge_threshold": 10,
    "min_line_length": 50,
    "header_height_ratio": 0.2
  },
  "grades": {
    "min_value": 0,
    "max_value": 20,
    "absent_keywords": ["A", "ABS", "ABSENT"],
    "absent_policy": "KEEP"
  },
  "templates": {
    "70": {
      "columns": 7,
      "drop_indices": [0, 4, 5],
      "grade_columns": [6],
      "excel_headers": ["CIN", "Nom & Prenom FR", "70%"]
    },
    "30": {
      "columns": 5,
      "drop_indices": [0],
      "grade_columns": [3, 4],
      "excel_headers": ["CIN", "Nom & Prenom FR", "20%", "10%"]
    },
    "40_40_20": {
      "columns": 6,
      "drop_indices": [0],
      "grade_columns": [3, 4, 5],
      "excel_headers": ["CIN", "Nom & Prenom FR", "40%", "40%", "20%"]
    }
  }
}
""")
    
    # ========================================================================
    # 3. models/data_models.py
    # ========================================================================
    create_file(base_dir / "models" / "data_models.py", """
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

class GradeType(Enum):
    NUMERIC = "numeric"
    ABSENT = "absent"
    INVALID = "invalid"

@dataclass
class GradeValue:
    '''Represents a single grade with metadata'''
    raw: str                    # Original OCR text
    type: GradeType             # Classification
    value: Optional[float]      # Numeric value if valid
    confidence: float = 0.0     # OCR confidence score
    
    def is_valid(self) -> bool:
        return self.type in [GradeType.NUMERIC, GradeType.ABSENT]
    
    def needs_review(self) -> bool:
        return self.type == GradeType.INVALID or self.confidence < 0.5

@dataclass
class StudentRow:
    '''Represents one student's data'''
    cin: str
    name: str
    grades: List[GradeValue]
    row_index: int
    
    def to_dict(self, headers: List[str], absent_policy: str) -> Dict[str, Any]:
        '''Convert to dict for Excel export'''
        result = {
            headers[0]: self.cin,
            headers[1]: self.name
        }
        
        for i, grade in enumerate(self.grades):
            col_name = headers[i + 2]  # Skip CIN and Name
            result[col_name] = self._resolve_grade(grade, absent_policy)
        
        return result
    
    def _resolve_grade(self, grade: GradeValue, policy: str) -> Any:
        if grade.type == GradeType.NUMERIC:
            return grade.value
        
        if grade.type == GradeType.ABSENT:
            if policy == "KEEP":
                return "ABS"
            elif policy == "ZERO":
                return 0
            elif policy == "EMPTY":
                return ""
        
        return ""  # Invalid

@dataclass
class Cell:
    '''Represents a table cell with geometry'''
    x: int
    y: int
    width: int
    height: int
    row_idx: int
    col_idx: int
    
    def center(self) -> tuple:
        return (self.x + self.width // 2, self.y + self.height // 2)

@dataclass
class TableStructure:
    '''Complete table structure'''
    cells: List[List[Cell]]        # 2D array [row][col]
    num_rows: int
    num_cols: int
    template_type: str              # "70", "30", or "40_40_20"
    header_rows: int = 1
    
    def get_cell(self, row: int, col: int) -> Optional[Cell]:
        if 0 <= row < self.num_rows and 0 <= col < self.num_cols:
            return self.cells[row][col]
        return None

@dataclass
class DocumentMetadata:
    '''Metadata extracted from document header'''
    groupe: str
    matiere: str
    template_type: str
    page_number: int
    
    def generate_filename(self) -> str:
        '''Generate Excel filename'''
        # Clean strings for filename
        g = self.groupe.replace(" ", "_").replace("/", "_")
        m = self.matiere.replace(" ", "_").replace("/", "_")
        return f"{g}_{m}_{self.template_type}.xlsx"

@dataclass
class ProcessingResult:
    '''Result of processing one PDF page'''
    metadata: DocumentMetadata
    students: List[StudentRow]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    def success_rate(self) -> float:
        if not self.students:
            return 0.0
        
        total_grades = sum(len(s.grades) for s in self.students)
        valid_grades = sum(
            sum(1 for g in s.grades if g.is_valid())
            for s in self.students
        )
        
        return valid_grades / total_grades if total_grades > 0 else 0.0
""")
    
    # ========================================================================
    # 4. models/__init__.py
    # ========================================================================
    create_file(base_dir / "models" / "__init__.py", """
from .data_models import (
    GradeType,
    GradeValue,
    StudentRow,
    Cell,
    TableStructure,
    DocumentMetadata,
    ProcessingResult
)

__all__ = [
    'GradeType',
    'GradeValue',
    'StudentRow',
    'Cell',
    'TableStructure',
    'DocumentMetadata',
    'ProcessingResult'
]
""")
    
    # ========================================================================
    # 5. core/geometry.py
    # ========================================================================
    create_file(base_dir / "core" / "geometry.py", """
import cv2
import numpy as np
from typing import List, Tuple, Optional
from models.data_models import Cell, TableStructure

class GeometryDetector:
    '''Detects table structure using OpenCV - NO ML'''
    
    def __init__(self, config: dict):
        self.merge_threshold = config['geometry']['line_merge_threshold']
        self.min_line_length = config['geometry']['min_line_length']
    
    def detect_table(self, image: np.ndarray) -> TableStructure:
        '''Main entry point - detects complete table structure'''
        
        # Preprocess
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # Detect lines
        h_lines = self._detect_horizontal_lines(binary)
        v_lines = self._detect_vertical_lines(binary)
        
        # Merge double lines
        h_lines = self._merge_parallel_lines(h_lines, horizontal=True)
        v_lines = self._merge_parallel_lines(v_lines, horizontal=False)
        
        # Build grid
        cells = self._build_grid(h_lines, v_lines, image.shape)
        
        # Determine template
        num_cols = len(v_lines) - 1
        template = self._classify_template(num_cols)
        
        return TableStructure(
            cells=cells,
            num_rows=len(h_lines) - 1,
            num_cols=num_cols,
            template_type=template
        )
    
    def _detect_horizontal_lines(self, binary: np.ndarray) -> List[int]:
        '''Detect horizontal lines using morphology'''
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        detected = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(
            detected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Extract y-coordinates
        lines = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > self.min_line_length:
                lines.append(y)
        
        return sorted(set(lines))
    
    def _detect_vertical_lines(self, binary: np.ndarray) -> List[int]:
        '''Detect vertical lines using morphology'''
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        detected = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        contours, _ = cv2.findContours(
            detected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        lines = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if h > self.min_line_length:
                lines.append(x)
        
        return sorted(set(lines))
    
    def _merge_parallel_lines(
        self, lines: List[int], horizontal: bool
    ) -> List[int]:
        '''Merge double/thick lines that are close together'''
        if not lines:
            return []
        
        merged = [lines[0]]
        
        for line in lines[1:]:
            if line - merged[-1] < self.merge_threshold:
                # Replace last with average
                merged[-1] = (merged[-1] + line) // 2
            else:
                merged.append(line)
        
        return merged
    
    def _build_grid(
        self, h_lines: List[int], v_lines: List[int], shape: tuple
    ) -> List[List[Cell]]:
        '''Build 2D grid of cells from line intersections'''
        cells = []
        
        for row_idx in range(len(h_lines) - 1):
            row = []
            y1, y2 = h_lines[row_idx], h_lines[row_idx + 1]
            
            for col_idx in range(len(v_lines) - 1):
                x1, x2 = v_lines[col_idx], v_lines[col_idx + 1]
                
                cell = Cell(
                    x=x1, y=y1,
                    width=x2 - x1,
                    height=y2 - y1,
                    row_idx=row_idx,
                    col_idx=col_idx
                )
                row.append(cell)
            
            cells.append(row)
        
        return cells
    
    def _classify_template(self, num_cols: int) -> str:
        '''Classify template based on column count'''
        if num_cols == 7:
            return "70"
        elif num_cols == 5:
            return "30"
        elif num_cols == 6:
            return "40_40_20"
        else:
            raise ValueError(f"Unknown template: {num_cols} columns")
    
    def visualize_grid(self, image: np.ndarray, table: TableStructure) -> np.ndarray:
        '''Draw grid on image for debugging'''
        vis = image.copy()
        
        for row in table.cells:
            for cell in row:
                cv2.rectangle(
                    vis,
                    (cell.x, cell.y),
                    (cell.x + cell.width, cell.y + cell.height),
                    (0, 255, 0), 2
                )
        
        return vis
""")
    # ============================================================================
    # 6. core/ocr.py
    # ============================================================================
    create_file(base_dir / "core" / "ocr.py", """
import cv2
import numpy as np
import pytesseract
from typing import Optional
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import torch

class OCREngine:
    '''Handles both printed (Tesseract) and handwritten (TrOCR) text'''
    
    def __init__(self, config: dict):
        self.tesseract_lang = config['ocr']['tesseract_lang']
        
        # Initialize TrOCR for handwriting
        self.trocr_processor = TrOCRProcessor.from_pretrained(
            config['ocr']['trocr_model']
        )
        self.trocr_model = VisionEncoderDecoderModel.from_pretrained(
            config['ocr']['trocr_model']
        )
        
        # Use GPU if available
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.trocr_model.to(self.device)
    
    def ocr_printed_text(
        self, cell_image: np.ndarray, whitelist: Optional[str] = None
    ) -> tuple[str, float]:
        '''OCR for printed text (CIN, names) using Tesseract'''
        
        # Preprocess
        gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Configure Tesseract
        config = f'--psm 7 -l {self.tesseract_lang}'
        if whitelist:
            config += f' -c tessedit_char_whitelist={whitelist}'
        
        # Run OCR
        data = pytesseract.image_to_data(
            binary, config=config, output_type=pytesseract.Output.DICT
        )
        
        # Extract text and confidence
        texts = [
            data['text'][i] for i in range(len(data['text']))
            if data['conf'][i] > 0
        ]
        confidences = [
            data['conf'][i] for i in range(len(data['conf']))
            if data['conf'][i] > 0
        ]
        
        text = ' '.join(texts).strip()
        conf = np.mean(confidences) / 100.0 if confidences else 0.0
        
        return text, conf
    
    def ocr_handwritten_number(self, cell_image: np.ndarray) -> tuple[str, float]:
        '''OCR for handwritten grades using TrOCR'''
        
        # Preprocess cell
        cell_image = self._preprocess_grade_cell(cell_image)
        
        # Convert to PIL
        pil_image = Image.fromarray(cv2.cvtColor(cell_image, cv2.COLOR_BGR2RGB))
        
        # Run TrOCR
        pixel_values = self.trocr_processor(
            pil_image, return_tensors="pt"
        ).pixel_values.to(self.device)
        
        with torch.no_grad():
            generated_ids = self.trocr_model.generate(pixel_values)
        
        text = self.trocr_processor.batch_decode(
            generated_ids, skip_special_tokens=True
        )[0]
        
        # TrOCR doesn't provide confidence directly, estimate from output
        confidence = self._estimate_confidence(text)
        
        return text, confidence
    
    def _preprocess_grade_cell(self, cell_image: np.ndarray) -> np.ndarray:
        '''Specialized preprocessing for grade cells'''
        
        # Remove borders (take inner 80%)
        h, w = cell_image.shape[:2]
        margin_x, margin_y = int(w * 0.1), int(h * 0.1)
        cropped = cell_image[margin_y:h-margin_y, margin_x:w-margin_x]
        
        # Normalize background
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        
        # Convert back to BGR for TrOCR
        return cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)
    
    def _estimate_confidence(self, text: str) -> float:
        '''Heuristic confidence estimation for TrOCR output'''
        
        # If text looks like a valid number or absence marker, higher confidence
        cleaned = text.strip().upper().replace(",", ".").replace(" ", "")
        
        if cleaned in ["A", "ABS", "ABSENT"]:
            return 0.9
        
        try:
            val = float(cleaned)
            if 0 <= val <= 20:
                return 0.85
            else:
                return 0.3  # Out of range
        except:
            return 0.2  # Garbage
""")

    # ============================================================================
    # 7. core/grade_parser.py
    # ============================================================================
    create_file(base_dir / "core" / "grade_parser.py", """
from models.data_models import GradeValue, GradeType

class GradeParser:
    '''Parse and validate grade values'''
    
    def __init__(self, config: dict):
        self.min_val = config['grades']['min_value']
        self.max_val = config['grades']['max_value']
        self.absent_keywords = config['grades']['absent_keywords']
    
    def parse(self, raw_text: str, confidence: float) -> GradeValue:
        '''Parse OCR text into GradeValue'''
        
        cleaned = raw_text.strip().upper().replace(",", ".").replace(" ", "")
        
        # Check for absence
        if cleaned in self.absent_keywords:
            return GradeValue(
                raw=raw_text,
                type=GradeType.ABSENT,
                value=None,
                confidence=confidence
            )
        
        # Try to parse as number
        try:
            value = float(cleaned)
            
            if self.min_val <= value <= self.max_val:
                return GradeValue(
                    raw=raw_text,
                    type=GradeType.NUMERIC,
                    value=value,
                    confidence=confidence
                )
            else:
                # Out of range
                return GradeValue(
                    raw=raw_text,
                    type=GradeType.INVALID,
                    value=None,
                    confidence=confidence
                )
        
        except ValueError:
            # Not a number, not absence -> invalid
            return GradeValue(
                raw=raw_text,
                type=GradeType.INVALID,
                value=None,
                confidence=confidence
            )
""")
    
    # ============================================================================
    # 8. core/metadata_extractor.py
    # ============================================================================

    create_file(base_dir / "core" / "metadata_extractor.py", """
import cv2
import numpy as np
import re
import pytesseract

class MetadataExtractor:
    '''Extract groupe and matiere from document header'''
    
    def __init__(self, config: dict):
        self.header_ratio = config['geometry']['header_height_ratio']
        self.tesseract_lang = config['ocr']['tesseract_lang']
    
    def extract(self, image: np.ndarray, page_num: int) -> tuple[str, str]:
        '''Extract metadata from top section of page'''
        
        # Crop top section (above table)
        h, w = image.shape[:2]
        header_h = int(h * self.header_ratio)
        header_section = image[0:header_h, :]
        
        # OCR the entire header
        text = pytesseract.image_to_string(
            header_section,
            lang=self.tesseract_lang
        )
        
        # Extract groupe and matiere
        groupe = self._extract_groupe(text)
        matiere = self._extract_matiere(text)
        
        return groupe, matiere
    
    def _extract_groupe(self, text: str) -> str:
        '''Extract "Nom Groupe" value'''
        
        patterns = [
            r'Nom Groupe[:\\s]+([^\\n]+)',
            r'Groupe[:\\s]+([^\\n]+)',
            r'Nom_Groupe[:\\s]+([^\\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._clean_value(match.group(1))
        
        return "GROUPE_INCONNU"
    
    def _extract_matiere(self, text: str) -> str:
        '''Extract matiere/EE value'''
        
        patterns = [
            r'EE[:\\s]+([^\\n]+)',
            r'Matière[:\\s]+([^\\n]+)',
            r'Matiére[:\\s]+([^\\n]+)',  # typo variant
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._clean_value(match.group(1))
        
        return "MATIERE_INCONNUE"
    
    def _clean_value(self, value: str) -> str:
        '''Clean extracted value for use in filename'''
        
        # Remove extra whitespace
        cleaned = ' '.join(value.split())
        
        # Remove problematic characters for filenames
        cleaned = re.sub(r'[<>:"/\\|?*]', '', cleaned)
        
        # Limit length
        if len(cleaned) > 50:
            cleaned = cleaned[:50]
        
        return cleaned.strip()
""")
    
    # ============================================================================
    # 9. core/excel_exporter.py
    # ============================================================================

    create_file(base_dir / "core" / "excel_exporter.py", """
import pandas as pd
from typing import List
from models.data_models import ProcessingResult, StudentRow

class ExcelExporter:
    '''Export processed data to Excel'''
    
    def __init__(self, config: dict):
        self.config = config
        self.templates = config['templates']
    
    def export(
        self, result: ProcessingResult, output_path: str, absent_policy: str
    ) -> str:
        '''Export to Excel file'''
        
        # Get template config
        template = self.templates[result.metadata.template_type]
        headers = template['excel_headers']
        
        # Build rows
        rows = []
        for student in result.students:
            row_dict = student.to_dict(headers, absent_policy)
            rows.append(row_dict)
        
        # Create DataFrame
        df = pd.DataFrame(rows)
        
        # Generate filename
        filename = result.metadata.generate_filename()
        full_path = f"{output_path}/{filename}"
        
        # Export
        df.to_excel(full_path, index=False, engine='openpyxl')
        
        return full_path
""")
    
    # ============================================================================
    # 10. README.md
    # ============================================================================

    create_file(base_dir / "README.md", """
# Système d'Extraction de Notes

Système automatisé d'extraction de notes depuis des relevés PDF scannés vers Excel.

## Caractéristiques

- **Détection géométrique pure** - Pas de machine learning pour la structure
- **OCR hybride** - Tesseract (imprimé) + TrOCR (manuscrit)
- **3 modèles supportés** - 30%, 70%, 40/40/20
- **Gestion des absences configurable** - Garder "ABS", convertir en 0, ou laisser vide
- **Interface en français** - PyQt5

## Installation

```bash
# Créer environnement virtuel
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate

# Installer dépendances
pip install -r requirements.txt

# Installer Tesseract OCR
# Linux: sudo apt-get install tesseract-ocr tesseract-ocr-fra
# Windows: télécharger depuis https://github.com/UB-Mannheim/tesseract/wiki
# Mac: brew install tesseract tesseract-lang
```

## Utilisation

```bash
python main.py
```

## Structure du Projet

- `core/` - Logique de traitement
  - `geometry.py` - Détection de tableau
  - `ocr.py` - Moteurs OCR
  - `grade_parser.py` - Validation des notes
  - `metadata_extractor.py` - Extraction groupe/matière
  - `excel_exporter.py` - Génération Excel

- `models/` - Modèles de données
- `ui/` - Interface PyQt5
- `utils/` - Utilitaires

## Configuration

Modifiez `config.json` pour ajuster:
- Seuils de détection géométrique
- Modèles OCR
- Politique des absences
- En-têtes Excel

## Architecture Technique

### Phase 1: Géométrie
1. PDF → Image (300 DPI)
2. Détection lignes H/V (morphologie OpenCV)
3. Fusion des doubles lignes
4. Construction grille d'intersections

### Phase 2: Classification
- Comptage colonnes → type de modèle
- 7 cols → 70%
- 5 cols → 30%
- 6 cols → 40/40/20

### Phase 3: OCR ciblé
- Tesseract pour CIN/noms
- TrOCR pour notes manuscrites
- Validation [0-20]

### Phase 4: Export
- Excel: `{groupe}_{matiere}_{type}.xlsx`
- Politique d'absence appliquée

## Dépannage

**TrOCR lent?**
- Première utilisation télécharge le modèle (~500MB)
- Utiliser GPU si disponible (CUDA)

**Tesseract non trouvé?**
- Définir chemin: `pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'`

**Lignes non détectées?**
- Ajuster `line_merge_threshold` dans config.json
- Augmenter résolution DPI

## Licence

Projet interne - Tous droits réservés
""")
    
    # ========================================================================
    # 11. core/__init__.py
    # ========================================================================
    create_file(base_dir / "core" / "__init__.py", """
from .geometry import GeometryDetector

__all__ = ['GeometryDetector']
""")
    
    # ========================================================================
    # 12. main.py (SIMPLE TEST VERSION)
    # ========================================================================
    create_file(base_dir / "main.py", """
import sys
import json
from PyQt5.QtWidgets import QApplication
from ui.main_window import MainWindow

def load_config():
    '''Load configuration from config.json'''
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    '''Launch the application'''
    
    # Load config
    config = load_config()
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Système d'Extraction de Notes")
    
    # Create and show main window
    window = MainWindow(config)
    window.show()
    
    # Run
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
""")
    
    # ========================================================================
    # 13. README.md
    # ========================================================================
    create_file(base_dir / "README.md", """
# Système d'Extraction de Notes

Extraction automatisée de notes depuis des PDFs scannés vers Excel.

## Installation Rapide

```bash
cd grade_extraction
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate
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
""")
    # ========================================================================
    # 14. models/config_model.py
    # ========================================================================

    create_file(base_dir / "models" / "config_model.py", """
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class TemplateConfig:
    columns: int
    drop_indices: List[int]
    grade_columns: List[int]
    excel_headers: List[str]

@dataclass
class AppConfig:
    ocr_lang: str
    trocr_model: str
    dpi: int
    line_merge_threshold: int
    min_line_length: int
    header_height_ratio: float
    min_grade: float
    max_grade: float
    absent_keywords: List[str]
    absent_policy: str
    templates: Dict[str, TemplateConfig]
    
    @classmethod
    def from_dict(cls, config_dict: dict):
        '''Load from JSON config'''
        templates = {
            name: TemplateConfig(**tpl_config)
            for name, tpl_config in config_dict['templates'].items()
        }
        
        return cls(
            ocr_lang=config_dict['ocr']['tesseract_lang'],
            trocr_model=config_dict['ocr']['trocr_model'],
            dpi=config_dict['ocr']['dpi'],
            line_merge_threshold=config_dict['geometry']['line_merge_threshold'],
            min_line_length=config_dict['geometry']['min_line_length'],
            header_height_ratio=config_dict['geometry']['header_height_ratio'],
            min_grade=config_dict['grades']['min_value'],
            max_grade=config_dict['grades']['max_value'],
            absent_keywords=config_dict['grades']['absent_keywords'],
            absent_policy=config_dict['grades']['absent_policy'],
            templates=templates
        )
""")

    
    # ========================================================================
    # DONE
    # ========================================================================
    print()
    print("=" * 70)
    print("✓ PROJECT GENERATED SUCCESSFULLY!")
    print("=" * 70)
    print()
    print("Next steps:")
    print(f"1. cd {base_dir}")
    print("2. python -m venv venv")
    print("3. source venv/bin/activate  # Windows: venv\\Scripts\\activate")
    print("4. pip install -r requirements.txt")
    print("5. python main.py  # Should show 'ALL IMPORTS WORKING!'")
    print()

if __name__ == '__main__':
    generate_project()