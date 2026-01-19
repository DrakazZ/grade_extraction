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
