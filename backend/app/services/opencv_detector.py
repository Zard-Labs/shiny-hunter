"""OpenCV detection service for shiny detection and template matching."""
import cv2
import re
import difflib
import numpy as np
from typing import Optional, Dict, Tuple, List
from pathlib import Path
from app.config import settings
from app.utils.logger import logger

# All 25 valid English Pokemon natures
VALID_NATURES = [
    'Hardy', 'Lonely', 'Brave', 'Adamant', 'Naughty',
    'Bold', 'Docile', 'Relaxed', 'Impish', 'Lax',
    'Timid', 'Hasty', 'Serious', 'Jolly', 'Naive',
    'Modest', 'Mild', 'Quiet', 'Bashful', 'Rash',
    'Calm', 'Gentle', 'Sassy', 'Careful', 'Quirky'
]

# Set for O(1) lookup
VALID_NATURES_SET = set(VALID_NATURES)

# Uppercase versions for fuzzy matching against OCR output
VALID_NATURES_UPPER = [n.upper() for n in VALID_NATURES]
UPPER_TO_PROPER = {n.upper(): n for n in VALID_NATURES}


class OpenCVDetector:
    """
    OpenCV detector for:
    - Shiny detection (yellow star pixel counting)
    - Gender detection (blue/red color masking)
    - Template matching for UI navigation
    - Nature OCR text recognition
    """
    
    def __init__(self):
        self.templates: Dict[str, Optional[np.ndarray]] = {}
        self._ocr_engine = None  # Lazy-loaded RapidOCR engine
        
        # Color bounds for shiny detection (HSV)
        self.lower_yellow = np.array([20, 100, 150])
        self.upper_yellow = np.array([35, 255, 255])
        
        # Color bounds for gender detection (HSV)
        self.lower_blue = np.array([100, 150, 150])
        self.upper_blue = np.array([130, 255, 255])
        self.lower_red1 = np.array([0, 150, 150])
        self.upper_red1 = np.array([10, 255, 255])
        self.lower_red2 = np.array([160, 150, 150])
        self.upper_red2 = np.array([180, 255, 255])
    
    @property
    def ocr_engine(self):
        """Lazy-load the RapidOCR engine on first use."""
        if self._ocr_engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._ocr_engine = RapidOCR()
                logger.info("[OK] RapidOCR engine initialized")
            except ImportError:
                logger.error("rapidocr_onnxruntime not installed. Nature detection will return 'Unknown'.")
                self._ocr_engine = False  # Sentinel to avoid retrying
            except Exception as e:
                logger.error(f"Failed to initialize RapidOCR: {e}")
                self._ocr_engine = False
        return self._ocr_engine
    
    def load_templates(self, templates_dir: str = "templates"):
        """
        Load all template images for visual matching.
        
        Args:
            templates_dir: Directory containing template images
        """
        base_path = Path(__file__).parent.parent.parent / templates_dir / "pokemon_red"
        
        template_files = {
            'title': 'title_screen.png',
            'load': 'load_game.png',
            'nick': 'nickname_screen.png',
            'oak': 'oak_lab.png',
            'pokemon': 'pokemon_menu.png',
            'choose': 'choose_pokemon.png',
            'summary': 'summary_screen.png'
        }
        
        for key, filename in template_files.items():
            path = base_path / filename
            if path.exists():
                self.templates[key] = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                logger.info(f"Loaded template: {key}")
            else:
                self.templates[key] = None
                logger.warning(f"Template not found: {path}")
    
    def check_template(
        self,
        gray_frame: np.ndarray,
        template_name: str,
        threshold: Optional[float] = None
    ) -> Tuple[bool, float]:
        """
        Check if template matches in the frame.
        
        Args:
            gray_frame: Grayscale frame to search
            template_name: Name of template to match
            threshold: Match threshold (uses config default if None)
        
        Returns:
            Tuple of (match_found, confidence_score)
        """
        template = self.templates.get(template_name)
        if template is None:
            logger.warning(f"Template '{template_name}' not loaded")
            return False, 0.0
        
        # Get threshold from config or use provided
        if threshold is None:
            threshold = settings.template_thresholds.get(template_name, 0.80)
        
        try:
            result = cv2.matchTemplate(gray_frame, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            
            match_found = max_val > threshold
            
            return match_found, float(max_val)
        
        except Exception as e:
            logger.error(f"Error matching template {template_name}: {e}")
            return False, 0.0
    
    def detect_shiny(self, color_frame: np.ndarray) -> Tuple[bool, int]:
        """
        Detect shiny sparkle (yellow star pixels).
        
        Args:
            color_frame: Color frame (BGR format)
        
        Returns:
            Tuple of (is_shiny, pixel_count)
        """
        try:
            # Get shiny zone coordinates from config
            sz = settings.shiny_zone
            ux = sz.get('upper_x', 264)
            uy = sz.get('upper_y', 109)
            lx = sz.get('lower_x', 312)
            ly = sz.get('lower_y', 151)
            
            # Crop region of interest
            roi = color_frame[uy:ly, ux:lx]
            
            # Convert to HSV
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            # Apply yellow color mask
            yellow_mask = cv2.inRange(hsv, self.lower_yellow, self.upper_yellow)
            
            # Count yellow pixels
            yellow_pixels = cv2.countNonZero(yellow_mask)
            
            is_shiny = yellow_pixels > settings.yellow_star_threshold
            
            return is_shiny, yellow_pixels
        
        except Exception as e:
            logger.error(f"Error detecting shiny: {e}")
            return False, 0
    
    def detect_gender(self, color_frame: np.ndarray) -> str:
        """
        Detect Pokemon gender from color of gender symbol.
        
        Args:
            color_frame: Color frame (BGR format)
        
        Returns:
            Gender string: 'Male', 'Female', or 'Unknown'
        """
        try:
            # Get gender zone coordinates from config
            gz = settings.gender_zone
            ux = gz.get('upper_x', 284)
            uy = gz.get('upper_y', 68)
            lx = gz.get('lower_x', 311)
            ly = gz.get('lower_y', 92)
            
            # Crop region of interest
            roi = color_frame[uy:ly, ux:lx]
            
            # Convert to HSV
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            # Check for blue (male)
            blue_mask = cv2.inRange(hsv, self.lower_blue, self.upper_blue)
            blue_pixels = cv2.countNonZero(blue_mask)
            
            # Check for red (female)
            red_mask1 = cv2.inRange(hsv, self.lower_red1, self.upper_red1)
            red_mask2 = cv2.inRange(hsv, self.lower_red2, self.upper_red2)
            red_mask = cv2.bitwise_or(red_mask1, red_mask2)
            red_pixels = cv2.countNonZero(red_mask)
            
            # Determine gender
            if blue_pixels > settings.blue_gender_threshold:
                return 'Male'
            elif red_pixels > settings.red_gender_threshold:
                return 'Female'
            else:
                return 'Unknown'
        
        except Exception as e:
            logger.error(f"Error detecting gender: {e}")
            return 'Unknown'
    
    def _fuzzy_match_nature(self, ocr_word: str) -> str:
        """
        Fuzzy match an OCR-read word against the list of valid Pokemon natures.
        
        Uses difflib to find the closest match, handling common OCR errors
        like N→H, D→O in the GBA pixel font.
        
        Args:
            ocr_word: The word read by OCR (e.g., 'HAUGHTY', 'BOLO')
        
        Returns:
            Properly capitalized nature name or 'Unknown'
        """
        word_upper = ocr_word.upper().strip()
        
        # 1. Exact match
        if word_upper in UPPER_TO_PROPER:
            return UPPER_TO_PROPER[word_upper]
        
        # 2. Fuzzy match using difflib (cutoff 0.6 = 60% similarity)
        matches = difflib.get_close_matches(
            word_upper, VALID_NATURES_UPPER, n=1, cutoff=0.6
        )
        if matches:
            matched = UPPER_TO_PROPER[matches[0]]
            logger.info(f"OCR fuzzy matched '{ocr_word}' -> '{matched}'")
            return matched
        
        return 'Unknown'
    
    def detect_nature(self, color_frame: np.ndarray) -> str:
        """
        Detect Pokemon nature using OCR on the TRAINER MEMO text region.
        
        Reads the text from the summary screen's TRAINER MEMO area,
        then extracts the word before 'nature' (e.g., "NAUGHTY nature.").
        
        Args:
            color_frame: Color frame (BGR format) of the summary screen
        
        Returns:
            Nature name (capitalized, e.g., 'Naughty') or 'Unknown'
        """
        if self.ocr_engine is False:
            return 'Unknown'
        
        try:
            # Get nature text zone coordinates from config
            nz = settings.nature_text_zone
            ux = nz.get('upper_x', 0)
            uy = nz.get('upper_y', 300)
            lx = nz.get('lower_x', 350)
            ly = nz.get('lower_y', 380)
            
            # Crop the TRAINER MEMO text region
            roi = color_frame[uy:ly, ux:lx]
            
            # Scale up 2x with linear interpolation for better OCR on pixel art
            scaled = cv2.resize(roi, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
            
            # Run OCR on the color image (rapidocr_onnxruntime returns tuple)
            result, elapse = self.ocr_engine(scaled)
            
            if result is None:
                logger.debug("OCR returned no text for nature detection")
                return 'Unknown'
            
            # result is a list of [box, text, confidence]
            texts = [item[1] for item in result]
            full_text = ' '.join(texts)
            logger.debug(f"OCR text from nature zone: '{full_text}'")
            
            # Try to find the word before 'nature' (case-insensitive)
            match = re.search(r'(\w+)\s+nature', full_text, re.IGNORECASE)
            if match:
                nature_word = match.group(1)
                return self._fuzzy_match_nature(nature_word)
            
            # Fallback: find the text right before the "nature" entry
            # Sometimes OCR splits them into separate entries
            for i, item in enumerate(result):
                text = item[1].strip().lower()
                if text == 'nature' or text == 'nature.':
                    if i > 0:
                        nature_word = result[i - 1][1]
                        return self._fuzzy_match_nature(nature_word)
            
            logger.debug(f"No nature pattern found in OCR text: '{full_text}'")
            return 'Unknown'
        
        except Exception as e:
            logger.error(f"Error detecting nature via OCR: {e}")
            return 'Unknown'


# Global detector instance
opencv_detector = OpenCVDetector()
