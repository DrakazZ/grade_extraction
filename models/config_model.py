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
