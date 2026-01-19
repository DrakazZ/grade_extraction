import cv2
import numpy as np
from typing import List, Tuple, Optional
from models.data_models import Cell, TableStructure

class GeometryDetector:
    '''Detects table structure - finds table region first, then analyzes grid'''
    
    def __init__(self, config: dict):
        self.merge_threshold = config['geometry']['line_merge_threshold']
        self.min_line_length = config['geometry']['min_line_length']
        self.edge_margin = config['geometry'].get('edge_margin', 50)
        self.min_cell_width = config['geometry'].get('min_cell_width', 50)
        self.min_cell_height = config['geometry'].get('min_cell_height', 30)
    
    def detect_table(self, image: np.ndarray) -> TableStructure:
        '''Main entry point - detects complete table structure'''
        
        # Preprocess
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 11, 2
        )
        
        # NEW: Find the table region first
        table_bbox = self._find_table_region(binary, image.shape)
        
        if table_bbox:
            x, y, w, h = table_bbox
            print(f"  Table region: x={x}, y={y}, w={w}, h={h}")
            
            # Crop to table region only
            binary_cropped = binary[y:y+h, x:x+w]
        else:
            print("  Warning: Could not find table region, using full image")
            binary_cropped = binary
            x, y, w, h = 0, 0, image.shape[1], image.shape[0]
        
        # Detect lines within table region
        h_lines = self._detect_horizontal_lines(binary_cropped)
        v_lines = self._detect_vertical_lines(binary_cropped)
        
        # Adjust coordinates back to full image
        h_lines = [line + y for line in h_lines]
        v_lines = [line + x for line in v_lines]
        
        # Merge double lines
        h_lines = self._merge_parallel_lines(h_lines, horizontal=True)
        v_lines = self._merge_parallel_lines(v_lines, horizontal=False)
        
        # Filter by cell size
        h_lines = self._filter_by_cell_size(h_lines, self.min_cell_height, True)
        v_lines = self._filter_by_cell_size(v_lines, self.min_cell_width, False)
        
        print(f"  Final grid: {len(h_lines)-1} rows x {len(v_lines)-1} columns")
        print(f"  H-lines: {h_lines}")
        print(f"  V-lines: {v_lines}")
        
        # Build grid
        cells = self._build_grid(h_lines, v_lines, image.shape)
        
        # Determine template
        num_cols = len(v_lines) - 1

        template = self._classify_template(num_cols)
        
        return TableStructure(
            cells=cells,
            num_rows=len(h_lines) - 1,
            num_cols=num_cols,
            template_type=template
        )
    
    def _find_table_region(self, binary: np.ndarray, image_shape: tuple) -> Optional[Tuple[int, int, int, int]]:
        '''
        Find the bounding box of the main table by detecting the grid structure
        This helps ignore stray lines outside the table
        '''
        
        # Detect both horizontal and vertical lines
        kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 1))
        kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 50))
        
        lines_h = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_h)
        lines_v = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_v)
        
        # Combine horizontal and vertical lines
        table_structure = cv2.bitwise_or(lines_h, lines_v)
        
        # Dilate to connect nearby lines
        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        dilated = cv2.dilate(table_structure, kernel_dilate, iterations=2)
        
        # Find the largest contour (should be the table)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Get largest contour by area
        largest_contour = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest_contour)
        
        # Sanity check: table should occupy reasonable portion of image
        image_area = image_shape[0] * image_shape[1]
        table_area = w * h
        
        if table_area < 0.1 * image_area:  # Table too small
            print(f"  Warning: Detected table too small ({table_area/image_area*100:.1f}% of image)")
            return None
        
        if table_area > 0.95 * image_area:  # Table is basically whole image
            return None
        
        # Add small margin
        margin = 20
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(image_shape[1] - x, w + 2*margin)
        h = min(image_shape[0] - y, h + 2*margin)
        
        return (x, y, w, h)
    
    def _detect_horizontal_lines(self, binary: np.ndarray) -> List[int]:
        '''Detect horizontal lines'''
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        detected = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        contours, _ = cv2.findContours(
            detected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        lines = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # Line must span at least 30% of the cropped region width
            if w > max(self.min_line_length, binary.shape[1] * 0.3):
                lines.append(y)
        
        return sorted(set(lines))
    
    def _detect_vertical_lines(self, binary: np.ndarray) -> List[int]:
        '''Detect vertical lines'''
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        detected = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        
        contours, _ = cv2.findContours(
            detected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        lines = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # Line must span at least 30% of the cropped region height
            if h > max(self.min_line_length, binary.shape[0] * 0.3):
                lines.append(x)
        
        return sorted(set(lines))
    
    def _merge_parallel_lines(self, lines: List[int], horizontal: bool) -> List[int]:
        '''Merge double/thick lines that are close together'''
        if not lines:
            return []
        
        merged = [lines[0]]
        
        for line in lines[1:]:
            if line - merged[-1] < self.merge_threshold:
                merged[-1] = (merged[-1] + line) // 2
            else:
                merged.append(line)
        
        return merged
    
    def _filter_by_cell_size(self, lines: List[int], min_size: int, horizontal: bool) -> List[int]:
        '''Remove lines that would create cells smaller than min_size'''
        if len(lines) <= 2:
            return lines
        
        filtered = [lines[0]]
        
        for i in range(1, len(lines) - 1):
            if lines[i] - filtered[-1] >= min_size:
                filtered.append(lines[i])
        
        filtered.append(lines[-1])
        
        return filtered
    
    def _build_grid(self, h_lines: List[int], v_lines: List[int], shape: tuple) -> List[List[Cell]]:
        '''Build 2D grid of cells from line intersections'''
        cells = []
        
        for row_idx in range(len(h_lines) - 1):
            row = []
            y1, y2 = h_lines[row_idx], h_lines[row_idx + 1]
            
            for col_idx in range(len(v_lines) - 1):
                x1, x2 = v_lines[col_idx], v_lines[col_idx + 1]
                
                cell = Cell(
                    x=x1, y=y1,
                    width=x2 - x1,
                    height=y2 - y1,
                    row_idx=row_idx,
                    col_idx=col_idx
                )
                row.append(cell)
            
            cells.append(row)
        
        return cells
    
    def _classify_template(self, num_cols: int) -> str:
            '''Classify template based on column count'''
            if num_cols == 7:
                return "70"
            elif num_cols == 5:
                return "30"
            elif num_cols == 6:
                return "40_40_20"
            else:
                raise ValueError(f"Unknown template: {num_cols} columns")
        
    def visualize_grid(self, image: np.ndarray, table: TableStructure) -> np.ndarray:
        '''Draw grid on image for debugging'''
        vis = image.copy()
        
        for row in table.cells:
            for cell in row:
                cv2.rectangle(
                    vis,
                    (cell.x, cell.y),
                    (cell.x + cell.width, cell.y + cell.height),
                    (0, 255, 0), 2
                )
                # Draw cell index
                cv2.putText(
                    vis,
                    f"r{cell.row_idx}c{cell.col_idx}",
                    (cell.x + 5, cell.y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (255, 0, 0),
                    1
                )
        
        return vis