# ============================================================================
# FILE: ui/main_window.py
# Main PyQt5 window for the grade extraction system
# ============================================================================

import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QListWidget, QTextEdit, QGroupBox,
    QComboBox, QProgressBar, QTableWidget, QTableWidgetItem,
    QMessageBox, QSplitter , QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor
import json

import cv2

# Import core processing modules
from core.geometry import GeometryDetector
from core.ocr import OCREngine
from core.grade_parser import GradeParser
from core.metadata_extractor import MetadataExtractor
from core.excel_exporter import ExcelExporter
from models.data_models import ProcessingResult, StudentRow, DocumentMetadata
from utils.deskew import deskew

# ============================================================================
# WORKER THREAD FOR PROCESSING
# ============================================================================
class ProcessingWorker(QThread):
    '''Background thread for processing PDFs'''
    
    progress = pyqtSignal(str, str)  # message, type (info/success/error)
    result_ready = pyqtSignal(object)  # ProcessingResult
    finished = pyqtSignal()
    
    def __init__(self, pdf_files, config, absent_policy):
        super().__init__()
        self.pdf_files = pdf_files
        self.config = config
        self.absent_policy = absent_policy
        
        # Initialize processors
        self.geometry = GeometryDetector(config)
        self.ocr = OCREngine(config)
        self.parser = GradeParser(config)
        self.metadata_extractor = MetadataExtractor(config)
        self.exporter = ExcelExporter(config)
    
    def run(self):
        '''Process all PDFs'''
        
        for pdf_path in self.pdf_files:
            try:
                self.progress.emit(f"Traitement: {os.path.basename(pdf_path)}", "info")
                result = self.process_single_pdf(pdf_path)
                
                if result:
                    self.result_ready.emit(result)
                    self.progress.emit(
                        f"✓ {result.metadata.generate_filename()} généré",
                        "success"
                    )
            
            except Exception as e:
                self.progress.emit(f"✗ Erreur: {str(e)}", "error")
        
        self.finished.emit()
    
    def process_single_pdf(self, pdf_path):
        '''Process one PDF page - REAL IMPLEMENTATION'''
        
        from pdf2image import convert_from_path
        import numpy as np
        from models.data_models import GradeValue, StudentRow, DocumentMetadata
        
        # Step 1: Convert PDF to image
        self.progress.emit("→ Conversion PDF en image", "info")
        try:
            images = convert_from_path(pdf_path, dpi=self.config['ocr']['dpi'])
            if not images:
                raise ValueError("No pages found in PDF")
            
            # Process first page only
            image = np.array(images[0])
            
        except Exception as e:
            raise Exception(f"PDF conversion failed: {str(e)}")
        
        # Step 2: Detect table geometry
        self.progress.emit("→ Détection géométrique du tableau", "info")
        try:
            table_structure = self.geometry.detect_table(image)
            num_cols = table_structure.num_cols
            self.progress.emit(f"→ Colonnes détectées: {num_cols}", "info")

            self.progress.emit(
                f"→ Classification: {table_structure.template_type}% détecté",
                "info"
            )

        except Exception as e:
            raise Exception(f"Table detection failed: {str(e)}")
        
        # Step 3: Extract metadata from header
        self.progress.emit("→ Extraction métadonnées", "info")
        try:
            groupe, matiere = self.metadata_extractor.extract(image, page_num=1)
        except Exception as e:
            self.progress.emit(f"⚠ Metadata extraction warning: {str(e)}", "info")
            groupe, matiere = "GROUPE_INCONNU", "MATIERE_INCONNUE"
        
        # Create metadata object
        metadata = DocumentMetadata(
            groupe=groupe,
            matiere=matiere,
            template_type=table_structure.template_type,
            page_number=1
        )
        
        # Step 4: Get template configuration
        template = self.config['templates'][table_structure.template_type]
        drop_cols = set(template['drop_indices'])  # Use set for O(1) lookup
        grade_cols = set(template['grade_columns'])
        
        # Step 5: Determine which original columns map to CIN, Name, Grades
        # Based on template config:
        # - First non-dropped column = CIN
        # - Second non-dropped column = Name
        # - Remaining columns in grade_columns = Grades
        
        kept_columns = [i for i in range(table_structure.num_cols) if i not in drop_cols]
        
        if len(kept_columns) < 2:
            raise Exception(f"Not enough columns after dropping. Kept: {kept_columns}")
        
        cin_col_idx = kept_columns[0]
        name_col_idx = kept_columns[1]
        grade_col_indices = [col for col in kept_columns[2:] if col in grade_cols]
        
        self.progress.emit(
            f"→ Mapping: CIN=col{cin_col_idx}, Name=col{name_col_idx}, Grades=cols{grade_col_indices}",
            "info"
        )
        
        # Step 6: Process each row (skip header row)
        self.progress.emit("→ OCR des cellules", "info")
        students = []
        
        for row_idx in range(table_structure.header_rows, table_structure.num_rows):
            try:
                row_cells = table_structure.cells[row_idx]
                
                # Extract CIN
                cin_cell = row_cells[cin_col_idx]
                cin_image = image[
                    cin_cell.y:cin_cell.y + cin_cell.height,
                    cin_cell.x:cin_cell.x + cin_cell.width
                ]

                cin_text, _ = self.ocr.ocr_printed_text(
                    cin_image, 
                    whitelist='0123456789'
                )
                
                cin_cleaned = cin_text.strip()
                if len(cin_cleaned) != 8:
                    self.progress.emit(f"⚠ ligne {row_idx}: CIN a valider '{cin_cleaned}'", "info")

                # Extract Name
                name_cell = row_cells[name_col_idx]
                name_image = image[
                    name_cell.y:name_cell.y + name_cell.height,
                    name_cell.x:name_cell.x + name_cell.width
                ]
                

                name_text, _ = self.ocr.ocr_printed_text(name_image)

                # Extract grades
                grades = []
                for grade_col_idx in grade_col_indices:
                    grade_cell = row_cells[grade_col_idx]
                    grade_image = image[
                        grade_cell.y:grade_cell.y + grade_cell.height,
                        grade_cell.x:grade_cell.x + grade_cell.width
                    ]
                    
                    # Use TrOCR for handwritten grades
                    grade_text, grade_conf = self.ocr.ocr_handwritten_number(grade_image)
                    
                    # Parse the grade
                    grade_value = self.parser.parse(grade_text, grade_conf)
                    grades.append(grade_value)
                
                # Create student row
                student = StudentRow(
                    cin=cin_cleaned,
                    name=name_text.strip(),
                    grades=grades,
                    row_index=row_idx
                )
                students.append(student)
                
            except Exception as e:
                self.progress.emit(
                    f"⚠ Row {row_idx} error: {str(e)}", 
                    "info"
                )
                continue
        
        # Step 7: Validate results
        self.progress.emit("→ Validation des notes", "info")
        
        if not students:
            raise Exception("No students extracted from document")
        
        self.progress.emit(f"→ {len(students)} étudiants extraits", "info")
        
        # Create result
        result = ProcessingResult(
            metadata=metadata,
            students=students,
            errors=[],
            warnings=[]
        )
        
        return result

# ============================================================================
# MAIN WINDOW
# ============================================================================
class MainWindow(QMainWindow):
    '''Main application window'''
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.pdf_files = []
        self.results = []
        self.absent_policy = config['grades']['absent_policy']
        
        self.init_ui()
    
    def init_ui(self):
        '''Initialize user interface'''
        
        self.setWindowTitle("Système d'Extraction de Notes")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        layout = QVBoxLayout()
        central.setLayout(layout)
        
        # Header
        header = self.create_header()
        layout.addWidget(header)
        
        # Settings panel
        settings = self.create_settings_panel()
        layout.addWidget(settings)
        
        # Splitter for file list and log
        splitter = QSplitter(Qt.Horizontal)
        
        # Left: File selection
        file_panel = self.create_file_panel()
        splitter.addWidget(file_panel)
        
        # Right: Processing log
        log_panel = self.create_log_panel()
        splitter.addWidget(log_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Results table
        results_panel = self.create_results_panel()
        layout.addWidget(results_panel)
        
        # Apply styles
        self.apply_styles()
    
    def create_header(self):
        '''Create header section'''
        
        group = QGroupBox()
        layout = QHBoxLayout()
        
        title = QLabel("📄 Système d'Extraction de Notes")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        layout.addWidget(title)
        
        layout.addStretch()
        
        subtitle = QLabel("Automatisation des relevés de notes")
        subtitle.setFont(QFont("Arial", 10))
        subtitle.setStyleSheet("color: #666;")
        layout.addWidget(subtitle)
        
        group.setLayout(layout)
        return group
    
    def create_settings_panel(self):
        '''Create settings panel'''
        
        group = QGroupBox("⚙️ Paramètres")
        layout = QHBoxLayout()
        
        label = QLabel("Gestion des absences (A, ABS):")
        layout.addWidget(label)
        
        self.absent_combo = QComboBox()
        self.absent_combo.addItems([
            "Conserver 'ABS' tel quel",
            "Convertir en 0",
            "Laisser vide"
        ])
        
        # Set initial value
        policy_map = {
            "KEEP": 0,
            "ZERO": 1,
            "EMPTY": 2
        }
        self.absent_combo.setCurrentIndex(
            policy_map.get(self.absent_policy, 0)
        )
        
        self.absent_combo.currentIndexChanged.connect(self.on_policy_changed)
        layout.addWidget(self.absent_combo)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def create_file_panel(self):
        '''Create file selection panel'''
        
        group = QGroupBox("1️⃣ Fichiers PDF")
        layout = QVBoxLayout()
        
        # File list
        self.file_list = QListWidget()
        layout.addWidget(self.file_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("➕ Ajouter")
        self.btn_add.clicked.connect(self.add_files)
        btn_layout.addWidget(self.btn_add)
        
        self.btn_clear = QPushButton("🗑️ Effacer")
        self.btn_clear.clicked.connect(self.clear_files)
        btn_layout.addWidget(self.btn_clear)
        
        layout.addLayout(btn_layout)
        
        # Process button
        self.btn_process = QPushButton("▶️ Traiter les fichiers")
        self.btn_process.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.btn_process.clicked.connect(self.process_files)
        self.btn_process.setEnabled(False)
        layout.addWidget(self.btn_process)
        
        group.setLayout(layout)
        return group
    
    def create_log_panel(self):
        '''Create processing log panel'''
        
        group = QGroupBox("2️⃣ Journal de traitement")
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Courier", 9))
        layout.addWidget(self.log_text)
        
        group.setLayout(layout)
        return group
    
    def create_results_panel(self):
        '''Create results table panel'''
        
        group = QGroupBox("3️⃣ Résultats")
        layout = QVBoxLayout()
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "Fichier Excel",
            "Groupe",
            "Matière",
            "Type",
            "Étudiants",
            "Action"
        ])
        
        # Adjust column widths
        self.results_table.setColumnWidth(0, 300)
        self.results_table.setColumnWidth(1, 200)
        self.results_table.setColumnWidth(2, 150)
        self.results_table.setColumnWidth(3, 80)
        self.results_table.setColumnWidth(4, 100)
        
        layout.addWidget(self.results_table)
        
        group.setLayout(layout)
        return group
    
    def apply_styles(self):
        '''Apply global styles'''
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding: 10px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QPushButton {
                padding: 8px 15px;
                border-radius: 4px;
                border: 1px solid #ccc;
                background-color: #f8f8f8;
            }
            QPushButton:hover {
                background-color: #e8e8e8;
            }
        """)
    
    def add_files(self):
        '''Add PDF files'''
        
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Sélectionner des fichiers PDF",
            "",
            "PDF Files (*.pdf)"
        )
        
        if files:
            self.pdf_files.extend(files)
            for f in files:
                self.file_list.addItem(os.path.basename(f))
            
            self.btn_process.setEnabled(len(self.pdf_files) > 0)
            self.add_log(f"{len(files)} fichier(s) ajouté(s)", "info")
    
    def clear_files(self):
        '''Clear file list'''
        
        self.pdf_files.clear()
        self.file_list.clear()
        self.btn_process.setEnabled(False)
        self.add_log("Liste effacée", "info")
    
    def on_policy_changed(self, index):
        '''Handle absent policy change'''
        
        policy_map = ["KEEP", "ZERO", "EMPTY"]
        self.absent_policy = policy_map[index]
        self.add_log(f"Politique d'absence: {self.absent_policy}", "info")
    
    def process_files(self):
        '''Start processing'''
        
        if not self.pdf_files:
            return
        
        # Clear previous results
        self.results.clear()
        self.results_table.setRowCount(0)
        self.log_text.clear()
        
        # Disable buttons
        self.btn_process.setEnabled(False)
        self.btn_add.setEnabled(False)
        self.btn_clear.setEnabled(False)
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        
        # Start worker thread
        self.worker = ProcessingWorker(
            self.pdf_files,
            self.config,
            self.absent_policy
        )
        
        self.worker.progress.connect(self.add_log)
        self.worker.result_ready.connect(self.add_result)
        self.worker.finished.connect(self.on_processing_finished)
        
        self.worker.start()
    
    def add_log(self, message, log_type="info"):
        '''Add message to log'''
        
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color coding
        color_map = {
            "info": "#333333",
            "success": "#4CAF50",
            "error": "#f44336"
        }
        
        color = color_map.get(log_type, "#333333")
        
        self.log_text.append(
            f'<span style="color: #999;">[{timestamp}]</span> '
            f'<span style="color: {color};">{message}</span>'
        )
    
    def add_result(self, result: ProcessingResult):
        '''Add result to table'''
        
        self.results.append(result)
        
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        # Filename
        self.results_table.setItem(
            row, 0,
            QTableWidgetItem(result.metadata.generate_filename())
        )
        
        # Groupe
        self.results_table.setItem(
            row, 1,
            QTableWidgetItem(result.metadata.groupe)
        )
        
        # Matiere
        self.results_table.setItem(
            row, 2,
            QTableWidgetItem(result.metadata.matiere)
        )
        
        # Type
        self.results_table.setItem(
            row, 3,
            QTableWidgetItem(result.metadata.template_type + "%")
        )
        
        # Students count
        self.results_table.setItem(
            row, 4,
            QTableWidgetItem(str(len(result.students)))
        )
        
        # Download button
        btn_download = QPushButton("⬇️ Télécharger")
        btn_download.clicked.connect(
            lambda checked, r=result: self.download_excel(r)
        )
        self.results_table.setCellWidget(row, 5, btn_download)
    
    def download_excel(self, result: ProcessingResult):
        '''Download Excel file'''
        
        # Ask for save location
        filename = result.metadata.generate_filename()
        
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le fichier Excel",
            filename,
            "Excel Files (*.xlsx)"
        )
        
        if save_path:
            try:
                # Export
                exporter = ExcelExporter(self.config)
                output = exporter.export(result, os.path.dirname(save_path), self.absent_policy)
                
                # Rename to user's choice
                if output != save_path:
                    os.rename(output, save_path)
                
                self.add_log(f"✓ Fichier enregistré: {os.path.basename(save_path)}", "success")
                
                QMessageBox.information(
                    self,
                    "Succès",
                    f"Fichier enregistré avec succès!\n\n{save_path}"
                )
            
            except Exception as e:
                self.add_log(f"✗ Erreur d'export: {str(e)}", "error")
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Impossible d'enregistrer le fichier:\n{str(e)}"
                )
    
    def on_processing_finished(self):
        '''Handle processing completion'''
        
        # Hide progress bar
        self.progress_bar.setVisible(False)
        
        # Re-enable buttons
        self.btn_process.setEnabled(True)
        self.btn_add.setEnabled(True)
        self.btn_clear.setEnabled(True)
        
        self.add_log("✓ Traitement terminé!", "success")
        
        QMessageBox.information(
            self,
            "Terminé",
            f"Traitement terminé avec succès!\n\n"
            f"{len(self.results)} fichier(s) Excel généré(s)."
        )

# ============================================================================
# STANDALONE TEST
# ============================================================================
if __name__ == '__main__':
    import json
    
    # Load config
    with open('../config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    app = QApplication(sys.argv)
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec_())