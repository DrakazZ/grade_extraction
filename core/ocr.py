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
            config['ocr']['trocr_model'],
            use_fast=False
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
        
        # Enhanced preprocessing for printed text
        processed = cell_image
        
        # Try multiple Tesseract configurations
        configs = [
            f'--psm 6 -l {self.tesseract_lang}',  # Uniform block
            f'--psm 7 -l {self.tesseract_lang}',  # Single line
        ]
        
        if whitelist:
            configs = [f"{c} -c tessedit_char_whitelist={whitelist}" for c in configs]
        
        best_text = ""
        best_conf = 0.0
        
        for config in configs:
            try:
                data = pytesseract.image_to_data(
                    processed, config=config, output_type=pytesseract.Output.DICT
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
                
                # Keep result with highest confidence
                if conf > best_conf and text:
                    best_text = text
                    best_conf = conf
            
            except Exception as e:
                continue
        
        # Fallback to English if needed
        if not best_text and self.tesseract_lang != 'eng':
            try:
                config = f'--psm 6 -l eng'
                if whitelist:
                    config += f' -c tessedit_char_whitelist={whitelist}'
                
                data = pytesseract.image_to_data(
                    processed, config=config, output_type=pytesseract.Output.DICT
                )
                
                texts = [
                    data['text'][i] for i in range(len(data['text']))
                    if data['conf'][i] > 0
                ]
                confidences = [
                    data['conf'][i] for i in range(len(data['conf']))
                    if data['conf'][i] > 0
                ]
                
                best_text = ' '.join(texts).strip()
                best_conf = np.mean(confidences) / 100.0 if confidences else 0.0
            
            except Exception:
                pass
        # Post-process: remove common border artifacts
        best_text = self._clean_border_artifacts(best_text)
        
        return best_text, best_conf
    
    def _clean_border_artifacts(self, text: str) -> str:
        '''Remove common OCR artifacts from borders'''
        if not text:
            return text
        
        # Remove leading/trailing single characters that are likely borders
        # Common artifacts: | l 1 (from vertical lines)
        border_chars = {'|', 'l', '!', 'i'}
        
        # Remove leading artifacts
        while text and text[0] in border_chars:
            text = text[1:].strip()
        
        # Remove trailing artifacts (less aggressive)
        while text and len(text) > 1 and text[-1] in {'|', '!'}:
            text = text[:-1].strip()
        
        return text
    
    def _preprocess_printed_cell(self, cell_image: np.ndarray) -> np.ndarray:
        '''Enhanced preprocessing for printed text cells'''
        
        cropped = cell_image
        
        # Convert to grayscale
        if len(cropped.shape) == 3:
            gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        else:
            gray = cropped
        
        # Resize if too small
        if gray.shape[0] < 40:
            scale = 40 / gray.shape[0]
            new_width = int(gray.shape[1] * scale)
            gray = cv2.resize(gray, (new_width, 40), interpolation=cv2.INTER_CUBIC)
        
        # Special preprocessing for photocopied documents
        # Detect if this is a photocopy (high noise, low contrast)
        contrast = gray.std()
        
        if contrast < 40:  # Low contrast = likely photocopy
            # Aggressive contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
            enhanced = clahe.apply(gray)
        else:
            # Normal contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
        
        # Aggressive denoising for photocopies
        denoised = cv2.fastNlMeansDenoising(enhanced, None, h=12, templateWindowSize=7, searchWindowSize=21)
        
        # Sharpen text
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        sharpened = cv2.filter2D(denoised, -1, kernel)
        
        # Adaptive threshold (works better for photocopies)
        binary = cv2.adaptiveThreshold(
            sharpened, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11, 2
        )
        
        # Morphological cleanup to remove thin border lines
        # Remove vertical lines (borders) specifically
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5))
        no_borders = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
        
        # Fill small holes
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 1))
        cleaned = cv2.morphologyEx(no_borders, cv2.MORPH_CLOSE, horizontal_kernel)
        
        return cleaned
    
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
        '''Enhanced preprocessing for grade cells (handwritten)'''
        
        # Convert to grayscale
        gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
        
        # Enhance contrast for photocopies
        contrast = gray.std()
        if contrast < 40:
            # Low contrast = photocopy
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
            enhanced = clahe.apply(gray)
        else:
            # Normal
            enhanced = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(enhanced, None, h=10, templateWindowSize=7, searchWindowSize=21)
        
        # Convert back to BGR for TrOCR
        result = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
        
        return result
    
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