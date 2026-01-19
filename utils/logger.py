import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

class GradeExtractionLogger:
    '''Custom logger for the application'''
    
    def __init__(self, log_file: Optional[str] = None):
        '''Initialize logger'''
        
        self.logger = logging.getLogger('GradeExtraction')
        self.logger.setLevel(logging.DEBUG)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-8s %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '[%(levelname)s] %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (if specified)
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(detailed_formatter)
            self.logger.addHandler(file_handler)
    
    def debug(self, message: str):
        '''Log debug message'''
        self.logger.debug(message)
    
    def info(self, message: str):
        '''Log info message'''
        self.logger.info(message)
    
    def warning(self, message: str):
        '''Log warning message'''
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False):
        '''Log error message'''
        self.logger.error(message, exc_info=exc_info)
    
    def success(self, message: str):
        '''Log success message (info level with special formatting)'''
        self.logger.info(f"✓ {message}")
    
    def processing_step(self, step: str, details: str = ""):
        '''Log processing step'''
        if details:
            self.logger.info(f"→ {step}: {details}")
        else:
            self.logger.info(f"→ {step}")
    
    def separator(self):
        '''Log separator line'''
        self.logger.info("=" * 70)