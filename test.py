#!/usr/bin/env python3
"""
Debug script to test the processing pipeline step-by-step
Run this to verify each component works before using the full GUI
"""

import json
import sys
import numpy as np
from pdf2image import convert_from_path
import cv2

# Import your modules
from core.geometry import GeometryDetector
from core.ocr import OCREngine
from core.grade_parser import GradeParser
from core.metadata_extractor import MetadataExtractor
from models.data_models import StudentRow, DocumentMetadata, ProcessingResult

def load_config():
    """Load configuration"""
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def test_pdf_to_image(pdf_path, config):
    """Test Step 1: PDF to Image conversion"""
    print("\n" + "="*70)
    print("STEP 1: PDF to Image Conversion")
    print("="*70)
    
    try:
        images = convert_from_path(pdf_path, dpi=config['ocr']['dpi'])
        print(f"✓ Successfully converted PDF")
        print(f"  - Number of pages: {len(images)}")
        print(f"  - First page size: {images[0].size}")
        
        # Convert to numpy array
        image = np.array(images[0])
        print(f"  - Numpy array shape: {image.shape}")
        
        # Save for visual inspection
        cv2.imwrite('debug_output/01_original_image.png', cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        print(f"  - Saved to: debug_output/01_original_image.png")
        
        return image
    
    except Exception as e:
        print(f"✗ ERROR: {str(e)}")
        return None

def test_geometry_detection(image, config):
    """Test Step 2: Table Geometry Detection"""
    print("\n" + "="*70)
    print("STEP 2: Table Geometry Detection")
    print("="*70)
    
    try:
        detector = GeometryDetector(config)
        table_structure = detector.detect_table(image)
        
        print(f"✓ Table detected successfully")
        print(f"  - Template type: {table_structure.template_type}")
        print(f"  - Grid size: {table_structure.num_rows} rows x {table_structure.num_cols} cols")
        print(f"  - Total cells: {len(table_structure.cells) * len(table_structure.cells[0])}")
        
        # Visualize grid
        vis_image = detector.visualize_grid(image, table_structure)
        cv2.imwrite('debug_output/02_grid_overlay.png', cv2.cvtColor(vis_image, cv2.COLOR_RGB2BGR))
        print(f"  - Saved grid visualization to: debug_output/02_grid_overlay.png")
        
        return table_structure
    
    except Exception as e:
        print(f"✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def test_metadata_extraction(image, config):
    """Test Step 3: Metadata Extraction"""
    print("\n" + "="*70)
    print("STEP 3: Metadata Extraction")
    print("="*70)
    
    try:
        extractor = MetadataExtractor(config)
        groupe, matiere = extractor.extract(image, page_num=1)
        
        print(f"✓ Metadata extracted")
        print(f"  - Groupe: {groupe}")
        print(f"  - Matiere: {matiere}")
        
        return groupe, matiere
    
    except Exception as e:
        print(f"✗ ERROR: {str(e)}")
        print(f"  - Using defaults: GROUPE_INCONNU, MATIERE_INCONNUE")
        return "GROUPE_INCONNU", "MATIERE_INCONNUE"

def test_cell_ocr(image, table_structure, config):
    """Test Step 4: OCR on Sample Cells"""
    print("\n" + "="*70)
    print("STEP 4: OCR Testing (First Data Row)")
    print("="*70)
    
    try:
        ocr = OCREngine(config)
        parser = GradeParser(config)
        
        # Get template config
        template = config['templates'][table_structure.template_type]
        drop_cols = set(template['drop_indices'])
        grade_cols = set(template['grade_columns'])
        
        # Determine column mapping
        kept_columns = [i for i in range(table_structure.num_cols) if i not in drop_cols]
        cin_col_idx = kept_columns[0]
        name_col_idx = kept_columns[1]
        grade_col_indices = [col for col in kept_columns[2:] if col in grade_cols]
        
        print(f"  Column mapping:")
        print(f"    - CIN: column {cin_col_idx}")
        print(f"    - Name: column {name_col_idx}")
        print(f"    - Grades: columns {grade_col_indices}")
        
        # Test first data row (skip header)
        row_idx = table_structure.header_rows
        row_cells = table_structure.cells[row_idx]
        
        print(f"\n  Testing Row {row_idx}:")
        
        # CIN
        cin_cell = row_cells[cin_col_idx]
        cin_image = image[
            cin_cell.y:cin_cell.y + cin_cell.height,
            cin_cell.x:cin_cell.x + cin_cell.width
        ]
        cv2.imwrite(f'debug_output/03_cin_cell_row{row_idx}.png', cv2.cvtColor(cin_image, cv2.COLOR_RGB2BGR))
        cin_text, cin_conf = ocr.ocr_printed_text(cin_image, whitelist='0123456789')
        print(f"    - CIN: '{cin_text}' (confidence: {cin_conf:.2f})")
        
        # Name
        name_cell = row_cells[name_col_idx]
        name_image = image[
            name_cell.y:name_cell.y + name_cell.height,
            name_cell.x:name_cell.x + name_cell.width
        ]
        cv2.imwrite(f'debug_output/04_name_cell_row{row_idx}.png', cv2.cvtColor(name_image, cv2.COLOR_RGB2BGR))
        name_text, name_conf = ocr.ocr_printed_text(name_image)
        print(f"    - Name: '{name_text}' (confidence: {name_conf:.2f})")
        
        # Grades
        for i, grade_col_idx in enumerate(grade_col_indices):
            grade_cell = row_cells[grade_col_idx]
            grade_image = image[
                grade_cell.y:grade_cell.y + grade_cell.height,
                grade_cell.x:grade_cell.x + grade_cell.width
            ]
            cv2.imwrite(f'debug_output/05_grade{i}_cell_row{row_idx}.png', cv2.cvtColor(grade_image, cv2.COLOR_RGB2BGR))
            grade_text, grade_conf = ocr.ocr_handwritten_number(grade_image)
            grade_value = parser.parse(grade_text, grade_conf)
            print(f"    - Grade {i}: '{grade_text}' → {grade_value.type.value} = {grade_value.value} (conf: {grade_conf:.2f})")
        
        print("\n✓ OCR test completed - check debug_output/ for cell images")
        
    except Exception as e:
        print(f"✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    """Main debug runner"""
    
    import os
    os.makedirs('debug_output', exist_ok=True)
    
    if len(sys.argv) < 2:
        print("Usage: python debug_pipeline.py <pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    print("="*70)
    print("GRADE EXTRACTION DEBUG PIPELINE")
    print("="*70)
    print(f"Testing file: {pdf_path}")
    
    # Load config
    config = load_config()
    print(f"Config loaded: {list(config['templates'].keys())} templates available")
    
    # Test each step
    image = test_pdf_to_image(pdf_path, config)
    if image is None:
        print("\n✗ FAILED at PDF conversion")
        return
    
    table_structure = test_geometry_detection(image, config)
    if table_structure is None:
        print("\n✗ FAILED at geometry detection")
        return
    
    groupe, matiere = test_metadata_extraction(image, config)
    
    test_cell_ocr(image, table_structure, config)
    
    print("\n" + "="*70)
    print("DEBUG COMPLETE")
    print("="*70)
    print("Check the debug_output/ folder for visualizations")
    print("If geometry looks wrong, check:")
    print("  - line_merge_threshold in config.json")
    print("  - min_line_length in config.json")
    print("If OCR is poor, check:")
    print("  - Image quality/DPI")
    print("  - Cell cropping (margin_ratio in ocr.py)")

if __name__ == '__main__':
    main()