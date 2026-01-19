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
