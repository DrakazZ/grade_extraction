import cv2
import numpy as np
from typing import Tuple, Optional

class ImagePreprocessor:
    '''Image preprocessing utilities for OCR improvement'''
    
    @staticmethod
    def deskew(image: np.ndarray) -> np.ndarray:
        '''Correct image skew/rotation'''
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        # Detect lines using Hough transform
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
        
        if lines is None:
            return image
        
        # Calculate average angle
        angles = []
        for rho, theta in lines[:, 0]:
            angle = np.degrees(theta) - 90
            if -45 < angle < 45:
                angles.append(angle)
        
        if not angles:
            return image
        
        median_angle = np.median(angles)
        
        # Rotate image
        if abs(median_angle) > 0.5:
            h, w = image.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
            rotated = cv2.warpAffine(
                image, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE
            )
            return rotated
        
        return image
    
    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        '''Enhance image contrast using CLAHE'''
        
        if len(image.shape) == 3:
            # Convert to LAB color space
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE to L channel
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            
            # Merge back
            enhanced = cv2.merge([l, a, b])
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        else:
            # Grayscale
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(image)
        
        return enhanced
    
    @staticmethod
    def remove_noise(image: np.ndarray) -> np.ndarray:
        '''Remove salt-and-pepper noise'''
        
        if len(image.shape) == 3:
            # Apply bilateral filter (preserves edges)
            denoised = cv2.bilateralFilter(image, 9, 75, 75)
        else:
            # Apply median filter for grayscale
            denoised = cv2.medianBlur(image, 3)
        
        return denoised
    
    @staticmethod
    def binarize(image: np.ndarray, method='adaptive') -> np.ndarray:
        '''Convert to binary (black & white)'''
        
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        if method == 'adaptive':
            binary = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11, 2
            )
        elif method == 'otsu':
            _, binary = cv2.threshold(
                gray, 0, 255,
                cv2.THRESH_BINARY + cv2.THRESH_OTSU
            )
        else:
            _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        return binary
    
    @staticmethod
    def crop_cell(image: np.ndarray, cell, margin_ratio=0.1) -> np.ndarray:
        '''Crop a cell from image with optional margin'''
        
        x, y = cell.x, cell.y
        w, h = cell.width, cell.height
        
        # Add margin
        margin_x = int(w * margin_ratio)
        margin_y = int(h * margin_ratio)
        
        x1 = max(0, x + margin_x)
        y1 = max(0, y + margin_y)
        x2 = min(image.shape[1], x + w - margin_x)
        y2 = min(image.shape[0], y + h - margin_y)
        
        return image[y1:y2, x1:x2]
    
    @staticmethod
    def normalize_size(image: np.ndarray, target_height=64) -> np.ndarray:
        '''Resize image to target height while preserving aspect ratio'''
        
        h, w = image.shape[:2]
        
        if h == 0:
            return image
        
        ratio = target_height / h
        new_width = int(w * ratio)
        
        resized = cv2.resize(
            image,
            (new_width, target_height),
            interpolation=cv2.INTER_CUBIC
        )
        
        return resized
    
    @staticmethod
    def full_preprocessing_pipeline(image: np.ndarray) -> np.ndarray:
        '''Complete preprocessing pipeline for scanned documents'''
        
        # 1. Deskew
        deskewed = ImagePreprocessor.deskew(image)
        
        # 2. Remove noise
        denoised = ImagePreprocessor.remove_noise(deskewed)
        
        # 3. Enhance contrast
        enhanced = ImagePreprocessor.enhance_contrast(denoised)
        
        return enhanced