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
        self._nature_debug_counter = 0  # Counter for debug image filenames
        
        # Active detection config (set by load_detection_config)
        self._detection_config: Optional[Dict] = None
        
        # Default color bounds for shiny detection (HSV)
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
        Load all template images for visual matching (legacy path).
        
        Args:
            templates_dir: Directory containing template images
        """
        from app.config import is_packaged, get_user_data_path
        if is_packaged():
            base_path = get_user_data_path() / templates_dir / "pokemon_red"
        else:
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
    
    def load_templates_for_automation(self, template_id: str, image_map: Dict[str, str]):
        """
        Load template images for a specific automation template.
        
        Clears existing templates and loads from the per-template directory.
        The ``image_map`` maps template *keys* (as referenced in the
        automation definition) to filenames on disk.
        
        Args:
            template_id: UUID of the automation template
            image_map: Dict of {key: filename} pairs, e.g.
                       {"title_screen": "title_screen.png", ...}
        """
        from app.config import is_packaged, get_user_data_path
        if is_packaged():
            base_path = get_user_data_path() / "templates" / template_id
        else:
            base_path = Path(__file__).parent.parent.parent / "templates" / template_id
        
        self.templates.clear()
        loaded = 0
        
        for key, filename in image_map.items():
            path = base_path / filename
            if path.exists():
                self.templates[key] = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                loaded += 1
                logger.info(f"Loaded template: {key} ({filename})")
            else:
                self.templates[key] = None
                logger.warning(f"Template image not found: {path}")
        
        logger.info(f"Loaded {loaded}/{len(image_map)} templates for automation {template_id}")
    
    def load_detection_config(self, detection_config: Dict):
        """
        Load detection parameters from an automation template definition.
        
        Updates the shiny detection color bounds so ``detect_shiny_with_config``
        and the engine can use per-template settings.
        
        Args:
            detection_config: The ``detection`` section of a template definition
        """
        self._detection_config = detection_config
        
        # Update shiny color bounds if provided
        color_bounds = detection_config.get("color_bounds", {})
        lower = color_bounds.get("lower_hsv")
        upper = color_bounds.get("upper_hsv")
        if lower:
            self.lower_yellow = np.array(lower)
        if upper:
            self.upper_yellow = np.array(upper)
        
        logger.info(f"Detection config loaded: method={detection_config.get('method', 'default')}")
    
    def detect_shiny_with_config(self, color_frame: np.ndarray,
                                  detection_config: Optional[Dict] = None
                                  ) -> Tuple[bool, int]:
        """
        Detect shiny using per-template detection config.
        
        Falls back to global settings if no config is provided or
        if ``load_detection_config`` was never called.
        
        Args:
            color_frame: Color frame (BGR format)
            detection_config: Optional override; uses stored config if None
        
        Returns:
            Tuple of (is_shiny, pixel_count)
        """
        cfg = detection_config or self._detection_config
        
        if cfg is None:
            # Fall back to the legacy method
            return self.detect_shiny(color_frame)
        
        try:
            zone = cfg.get("zone", {})
            ux = zone.get("upper_x", 264)
            uy = zone.get("upper_y", 109)
            lx = zone.get("lower_x", 312)
            ly = zone.get("lower_y", 151)
            threshold = cfg.get("threshold", 20)
            
            roi = color_frame[uy:ly, ux:lx]
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            yellow_mask = cv2.inRange(hsv, self.lower_yellow, self.upper_yellow)
            yellow_pixels = cv2.countNonZero(yellow_mask)
            
            is_shiny = yellow_pixels > threshold
            return is_shiny, yellow_pixels
        
        except Exception as e:
            logger.error(f"Error detecting shiny (config mode): {e}")
            return False, 0
    
    def detect_gender_with_config(self, color_frame: np.ndarray,
                                   gender_config: Optional[Dict] = None
                                   ) -> str:
        """
        Detect gender using per-template zone config.
        
        Args:
            color_frame: Color frame (BGR format)
            gender_config: Optional gender_detection section from template
        
        Returns:
            Gender string: 'Male', 'Female', or 'Unknown'
        """
        if gender_config is None or not gender_config.get("enabled", True):
            return self.detect_gender(color_frame)
        
        zone = gender_config.get("zone", {})
        if not zone:
            return self.detect_gender(color_frame)
        
        try:
            ux = zone.get("upper_x", 284)
            uy = zone.get("upper_y", 68)
            lx = zone.get("lower_x", 311)
            ly = zone.get("lower_y", 92)
            
            roi = color_frame[uy:ly, ux:lx]
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            
            blue_mask = cv2.inRange(hsv, self.lower_blue, self.upper_blue)
            blue_pixels = cv2.countNonZero(blue_mask)
            
            red_mask1 = cv2.inRange(hsv, self.lower_red1, self.upper_red1)
            red_mask2 = cv2.inRange(hsv, self.lower_red2, self.upper_red2)
            red_mask = cv2.bitwise_or(red_mask1, red_mask2)
            red_pixels = cv2.countNonZero(red_mask)
            
            if blue_pixels > settings.blue_gender_threshold:
                return 'Male'
            elif red_pixels > settings.red_gender_threshold:
                return 'Female'
            else:
                return 'Unknown'
        
        except Exception as e:
            logger.error(f"Error detecting gender (config mode): {e}")
            return 'Unknown'
    
    def detect_nature_with_config(self, color_frame: np.ndarray,
                                   nature_config: Optional[Dict] = None
                                   ) -> str:
        """
        Detect nature using per-template zone config.
        
        Args:
            color_frame: Color frame (BGR format)
            nature_config: Optional nature_detection section from template
        
        Returns:
            Nature name or 'Unknown'
        """
        if nature_config is None or not nature_config.get("enabled", True):
            return self.detect_nature(color_frame)
        
        zone = nature_config.get("zone", {})
        if not zone:
            return self.detect_nature(color_frame)
        
        # Temporarily override settings for the OCR call
        # (detect_nature reads from settings.nature_text_zone)
        import copy
        original_zone = copy.deepcopy(settings.nature_text_zone)
        try:
            settings.nature_text_zone = zone
            return self.detect_nature(color_frame)
        finally:
            settings.nature_text_zone = original_zone
    
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
    
    def _save_nature_debug(self, roi: np.ndarray, scaled: np.ndarray,
                           reason: str, ocr_result=None, full_text: str = ""):
        """
        Save debug images and log OCR details when nature detection fails.
        
        Saves the raw ROI and upscaled image to encounters/debug/ so you can
        visually inspect what the OCR is working with.
        
        Args:
            roi: The raw cropped region of interest
            scaled: The upscaled image sent to OCR
            reason: Why detection failed (e.g., 'no_text', 'no_pattern', 'exception')
            ocr_result: Raw OCR result list (optional)
            full_text: Joined OCR text (optional)
        """
        try:
            self._nature_debug_counter += 1
            from app.config import is_packaged, get_user_data_path
            if is_packaged():
                debug_dir = get_user_data_path() / 'encounters' / 'debug'
            else:
                debug_dir = Path(__file__).parent.parent.parent / 'encounters' / 'debug'
            debug_dir.mkdir(parents=True, exist_ok=True)
            
            counter = self._nature_debug_counter
            
            # Save raw ROI crop
            roi_path = debug_dir / f"nature_{counter:04d}_roi.png"
            cv2.imwrite(str(roi_path), roi)
            
            # Save upscaled image (what OCR actually sees)
            scaled_path = debug_dir / f"nature_{counter:04d}_scaled.png"
            cv2.imwrite(str(scaled_path), scaled)
            
            # Log details at WARNING level so they always appear
            logger.warning(
                f"[Nature Debug #{counter}] reason={reason} | "
                f"roi_size={roi.shape[1]}x{roi.shape[0]} | "
                f"scaled_size={scaled.shape[1]}x{scaled.shape[0]} | "
                f"ocr_text='{full_text}' | "
                f"saved: {roi_path.name}, {scaled_path.name}"
            )
            
            # Log individual OCR entries with confidence scores
            if ocr_result:
                for i, item in enumerate(ocr_result):
                    text = item[1]
                    conf = item[2] if len(item) > 2 else 'N/A'
                    logger.warning(
                        f"  OCR entry[{i}]: text='{text}' confidence={conf}"
                    )
        except Exception as e:
            logger.error(f"Failed to save nature debug info: {e}")
    
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
            logger.warning("[Nature] OCR engine not available — returning Unknown")
            return 'Unknown'
        
        try:
            # Get nature text zone coordinates from config
            nz = settings.nature_text_zone
            ux = nz.get('upper_x', 0)
            uy = nz.get('upper_y', 300)
            lx = nz.get('lower_x', 350)
            ly = nz.get('lower_y', 380)
            
            h, w = color_frame.shape[:2]
            logger.info(
                f"[Nature] Frame size: {w}x{h} | "
                f"Zone: ({ux},{uy})->({lx},{ly}) | "
                f"crop_mode={settings.crop_mode}"
            )
            
            # Bounds check — clamp to frame dimensions
            uy_c = min(uy, h)
            ly_c = min(ly, h)
            ux_c = min(ux, w)
            lx_c = min(lx, w)
            if uy_c >= ly_c or ux_c >= lx_c:
                logger.warning(
                    f"[Nature] Zone out of bounds! Clamped: "
                    f"({ux_c},{uy_c})->({lx_c},{ly_c}) from frame {w}x{h}"
                )
                return 'Unknown'
            
            # Crop the TRAINER MEMO text region
            roi = color_frame[uy_c:ly_c, ux_c:lx_c]
            
            # Scale up 2x with linear interpolation for better OCR on pixel art
            scaled = cv2.resize(roi, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
            
            # Run OCR on the color image (rapidocr_onnxruntime returns tuple)
            result, elapse = self.ocr_engine(scaled)
            
            if result is None:
                logger.info("[Nature] OCR returned no text")
                self._save_nature_debug(roi, scaled, 'no_text')
                return 'Unknown'
            
            # result is a list of [box, text, confidence]
            texts = [item[1] for item in result]
            full_text = ' '.join(texts)
            logger.info(f"[Nature] OCR text: '{full_text}'")
            
            # Try to find the word before 'nature' (case-insensitive)
            match = re.search(r'(\w+)\s+nature', full_text, re.IGNORECASE)
            if match:
                nature_word = match.group(1)
                matched_nature = self._fuzzy_match_nature(nature_word)
                logger.info(f"[Nature] Regex matched word='{nature_word}' -> '{matched_nature}'")
                if matched_nature == 'Unknown':
                    self._save_nature_debug(
                        roi, scaled, f'fuzzy_fail_regex (word={nature_word})',
                        result, full_text
                    )
                return matched_nature
            
            # Fallback: find the text right before the "nature" entry
            # Sometimes OCR splits them into separate entries
            for i, item in enumerate(result):
                text = item[1].strip().lower()
                if text == 'nature' or text == 'nature.':
                    if i > 0:
                        nature_word = result[i - 1][1]
                        matched_nature = self._fuzzy_match_nature(nature_word)
                        logger.info(
                            f"[Nature] Fallback matched word='{nature_word}' -> '{matched_nature}'"
                        )
                        if matched_nature == 'Unknown':
                            self._save_nature_debug(
                                roi, scaled,
                                f'fuzzy_fail_fallback (word={nature_word})',
                                result, full_text
                            )
                        return matched_nature
            
            logger.info(f"[Nature] No 'nature' keyword found in OCR text: '{full_text}'")
            self._save_nature_debug(roi, scaled, 'no_pattern', result, full_text)
            return 'Unknown'
        
        except Exception as e:
            logger.error(f"[Nature] Exception during OCR: {e}")
            return 'Unknown'


# Global detector instance
opencv_detector = OpenCVDetector()
