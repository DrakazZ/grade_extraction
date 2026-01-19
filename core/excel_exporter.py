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
