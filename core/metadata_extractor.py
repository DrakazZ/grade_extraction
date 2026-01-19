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
            r'Nom Groupe[:\s]+([^\n]+)',
            r'Groupe[:\s]+([^\n]+)',
            r'Nom_Groupe[:\s]+([^\n]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._clean_value(match.group(1))
        
        return "GROUPE_INCONNU"
    
    def _extract_matiere(self, text: str) -> str:
        '''Extract matiere/EE value'''
        
        patterns = [
            r'EE[:\s]+([^\n]+)',
            r'Matière[:\s]+([^\n]+)',
            r'Matiére[:\s]+([^\n]+)',  # typo variant
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
        cleaned = re.sub(r'[<>:"/\|?*]', '', cleaned)
        
        # Limit length
        if len(cleaned) > 50:
            cleaned = cleaned[:50]
        
        return cleaned.strip()
