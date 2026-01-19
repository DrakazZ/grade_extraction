import cv2
import numpy as np
import pytesseract

def correct_orientation(img: np.ndarray) -> np.ndarray:
    """Rotate if landscape to portrait"""
    h, w = img.shape[:2]
    
    # If width > height, rotate 90° clockwise
    if w > h:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
        print(f"  Corrected orientation: landscape → portrait")
    
    return img


def deskew_image(img: np.ndarray, max_angle: float = 5.0) -> tuple[np.ndarray, float]:
    """
    Deskew image using minimum area rectangle
    
    Args:
        img: Input image
        max_angle: Maximum angle to correct (prevents over-rotation)
        
    Returns: (deskewed_image, angle_corrected)
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Invert for dark text on light background
    gray = cv2.bitwise_not(gray)
    
    # Threshold
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    
    # Find all foreground pixels
    coords = np.column_stack(np.where(thresh > 0))
    
    if coords.size == 0:
        print("  Warning: No foreground pixels found for deskewing")
        return img, 0.0
    
    # Get rotation angle from minimum area rectangle
    angle = cv2.minAreaRect(coords)[-1]
    
    # The angle returned by minAreaRect is in range [0, 90)
    # We need to correct it to get the actual skew angle
    # The rectangle can be oriented in two ways, we need to pick the right one
    
    # For angles > 45, the rectangle is oriented the "other way"
    if angle > 45:
        angle = angle - 90
    
    # Now angle is in range [-45, 45]
    print(f"  Raw detected skew: {angle:.2f}°")
    
    # Limit angle to prevent crazy rotations
    if abs(angle) > max_angle:
        print(f"  ⚠ Angle {angle:.2f}° exceeds limit {max_angle}°, skipping deskew")
        return img, 0.0
    
    # Skip if angle is negligible
    if abs(angle) < 0.3:
        print(f"  Skew angle too small ({angle:.2f}°), no correction needed")
        return img, 0.0
    
    print(f"  Applying correction: {angle:.2f}°")
    
    # Get image dimensions
    (h, w) = img.shape[:2]
    center = (w // 2, h // 2)
    
    # Calculate rotation matrix (NEGATIVE angle to correct the skew)
    M = cv2.getRotationMatrix2D(center, -angle, 1.0)
    
    # Calculate new bounding dimensions to prevent cropping
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    
    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))
    
    # Adjust translation component of matrix
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]
    
    # Perform rotation with white background
    rotated = cv2.warpAffine(
        img, M, (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)  # White background
    )
    
    return rotated, angle


def auto_crop_white_borders(img: np.ndarray, margin: int = 20) -> np.ndarray:
    """
    Crop white borders added by rotation
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Threshold to find content (anything not white)
    _, thresh = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    
    # Find all non-white pixels
    coords = np.column_stack(np.where(thresh > 0))
    
    if coords.size == 0:
        return img
    
    # Get bounding box
    y_min, x_min = coords.min(axis=0)
    y_max, x_max = coords.max(axis=0)
    
    # Add margin
    y_min = max(0, y_min - margin)
    x_min = max(0, x_min - margin)
    y_max = min(img.shape[0], y_max + margin)
    x_max = min(img.shape[1], x_max + margin)
    
    # Crop
    cropped = img[y_min:y_max, x_min:x_max]
    
    print(f"  Cropped borders: {img.shape[:2]} → {cropped.shape[:2]}")
    
    return cropped


def detect_rotation_tesseract(img: np.ndarray) -> int:
    """
    Detect rotation using Tesseract OSD (Orientation and Script Detection)
    Returns rotation angle needed to correct
    """
    try:
        osd = pytesseract.image_to_osd(img)
        
        for line in osd.split("\n"):
            if "Rotate" in line:
                angle = int(line.split(":")[-1].strip())
                if angle != 0:
                    print(f"  Tesseract detected rotation: {angle}°")
                return angle
        
        return 0
    
    except Exception as e:
        print(f"  Warning: Tesseract OSD failed: {e}")
        return 0


def deskew(img: np.ndarray, use_tesseract_osd: bool = False, max_angle: float = 5.0) -> np.ndarray:
    """
    Complete deskew pipeline
    
    Args:
        img: Input image (BGR)
        use_tesseract_osd: Whether to use Tesseract's OSD for additional rotation check
        max_angle: Maximum skew angle to correct (prevents over-rotation)
        
    Returns:
        Deskewed image
    """
    print("→ Deskewing image...")
    
    # Validate input
    if img is None or img.size == 0:
        print("  ✗ Invalid image, skipping deskew")
        return img
    
    # Step 1: Correct orientation (landscape → portrait)
    img = correct_orientation(img)
    
    # Step 2: Deskew using minAreaRect
    deskewed_img, angle = deskew_image(img, max_angle=max_angle)
    
    # Step 3: Optional - Use Tesseract OSD for 90/180/270° rotations
    if use_tesseract_osd:
        rotation_angle = detect_rotation_tesseract(deskewed_img)
        
        if rotation_angle == 90:
            deskewed_img = cv2.rotate(deskewed_img, cv2.ROTATE_90_COUNTERCLOCKWISE)
        elif rotation_angle == 180:
            deskewed_img = cv2.rotate(deskewed_img, cv2.ROTATE_180)
        elif rotation_angle == 270:
            deskewed_img = cv2.rotate(deskewed_img, cv2.ROTATE_90_CLOCKWISE)
    
    # Step 4: Crop white borders if rotation was applied
    if abs(angle) > 0.3:
        deskewed_img = auto_crop_white_borders(deskewed_img, margin=30)
    
    print("  ✓ Deskewing complete")
    
    return deskewed_img


def deskew_fast(img: np.ndarray, max_angle: float = 5.0) -> np.ndarray:
    """
    Fast deskew without Tesseract OSD
    Recommended for most cases
    
    Args:
        img: Input image
        max_angle: Maximum angle to correct (default 5°, prevents wild rotations)
    """
    return deskew(img, use_tesseract_osd=False, max_angle=max_angle)


def deskew_safe(img: np.ndarray) -> np.ndarray:
    """
    Ultra-safe deskew with very conservative angle limit
    Use this if you're getting wild rotations
    """
    return deskew(img, use_tesseract_osd=False, max_angle=3.0)