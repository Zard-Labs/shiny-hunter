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

# ── French nature support ─────────────────────────────────────────────
# French nature name → English equivalent (Gen III/IV Pokémon games)
FRENCH_TO_ENGLISH = {
    'Hardi':    'Hardy',
    'Solo':     'Lonely',
    'Brave':    'Brave',
    'Rigide':   'Adamant',
    'Mauvais':  'Naughty',
    'Assuré':   'Bold',
    'Docile':   'Docile',
    'Relax':    'Relaxed',
    'Malin':    'Impish',
    'Lâche':    'Lax',
    'Timide':   'Timid',
    'Pressé':   'Hasty',
    'Sérieux':  'Serious',
    'Jovial':   'Jolly',
    'Naïf':     'Naive',
    'Modeste':  'Modest',
    'Doux':     'Mild',
    'Discret':  'Quiet',
    'Pudique':  'Bashful',
    'Foufou':   'Rash',
    'Calme':    'Calm',
    'Gentil':   'Gentle',
    'Malpoli':  'Sassy',
    'Prudent':  'Careful',
    'Bizarre':  'Quirky',
}

# French nature names list (for fuzzy matching)
FRENCH_NATURES = list(FRENCH_TO_ENGLISH.keys())
FRENCH_NATURES_UPPER = [n.upper() for n in FRENCH_NATURES]
FRENCH_UPPER_TO_ENGLISH = {n.upper(): FRENCH_TO_ENGLISH[n] for n in FRENCH_NATURES}


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
    
    def check_template(
        self,
        gray_frame: np.ndarray,
        template_name: str,
        threshold: Optional[float] = None,
        roi: Optional[Dict[str, int]] = None
    ) -> Tuple[bool, float]:
        """
        Check if template matches in the frame.
        
        Args:
            gray_frame: Grayscale frame to search
            template_name: Name of template to match
            threshold: Match threshold (uses config default if None)
            roi: Optional region of interest dict with keys
                 ``x``, ``y``, ``width``, ``height``.  When provided the
                 search is limited to that rectangular sub-region of the
                 frame, improving both speed and accuracy.
        
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
            # Crop to ROI if provided
            if roi:
                rx = roi.get('x', 0)
                ry = roi.get('y', 0)
                rw = roi.get('width', 0)
                rh = roi.get('height', 0)
                fh, fw = gray_frame.shape[:2]
                # Clamp to frame bounds
                rx = max(0, min(rx, fw - 1))
                ry = max(0, min(ry, fh - 1))
                rw = min(rw, fw - rx)
                rh = min(rh, fh - ry)
                
                search_region = gray_frame[ry:ry + rh, rx:rx + rw]
                
                # Validate: ROI must be at least as large as template
                th, tw = template.shape[:2]
                if search_region.shape[0] < th or search_region.shape[1] < tw:
                    logger.warning(
                        f"ROI ({rw}x{rh}) too small for template "
                        f"'{template_name}' ({tw}x{th})"
                    )
                    return False, 0.0
            else:
                search_region = gray_frame
            
            result = cv2.matchTemplate(search_region, template, cv2.TM_CCOEFF_NORMED)
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

    # ================================================================
    #  Battle sparkle detection (multi-frame, variance-aware)
    # ================================================================

    def detect_battle_sparkle(
        self,
        frames: List[np.ndarray],
        zone: Dict[str, int],
        spark_threshold: int = 10,
        peak_threshold: int = 50,
        min_spike_frames: int = 3,
        lower_hsv: Optional[List[int]] = None,
        upper_hsv: Optional[List[int]] = None,
        spike_delta_pct: float = 0.15,
        min_variance: float = 50.0,
        debug_dir: Optional[str] = None,
        encounter_num: int = 0,
    ) -> Tuple[bool, Dict]:
        """
        Analyse a window of consecutive frames for the shiny sparkle
        animation that plays when a shiny Pokémon enters battle.

        Uses a **variance-aware** approach: instead of checking absolute
        bright-pixel counts against fixed thresholds (which false-positives
        on bright battle screens), the algorithm computes a *baseline*
        (median pixel count across frames) and looks for frames that spike
        significantly above that baseline.

        A shiny sparkle produces a brief brightness spike (some frames
        jump well above the baseline then drop back).  A normal encounter
        has roughly constant brightness across all frames (low variance).

        Args:
            frames:           List of BGR colour frames (newest last).
            zone:             ROI dict with keys upper_x, upper_y, lower_x, lower_y.
            spark_threshold:  Absolute per-frame minimum pixel count for a spike
                              (safety net, but the variance check is primary).
            peak_threshold:   Absolute peak bright-pixel count required (safety net).
            min_spike_frames: Minimum number of elevated frames above baseline.
            lower_hsv:        Lower HSV bound for sparkle colour [H, S, V].
                              Defaults to near-white/bright-yellow [0, 0, 200].
            upper_hsv:        Upper HSV bound for sparkle colour [H, S, V].
                              Defaults to [60, 100, 255].
            spike_delta_pct:  A frame must exceed baseline by this fraction to
                              count as elevated. E.g. 0.15 = 15% above median.
            min_variance:     Minimum standard deviation of per-frame counts
                              required to consider calling shiny.  Zero-variance
                              windows (constant brightness) are always normal.
            debug_dir:        Optional directory path to save ROI/mask debug images.
            encounter_num:    Current encounter number (used in debug filenames).

        Returns:
            Tuple of (is_shiny, details_dict).  *details_dict* contains:
                per_frame_counts  – list of int pixel counts per frame
                peak_count        – maximum count across all frames
                spike_frames      – number of frames exceeding spark_threshold
                elevated_frames   – frames above baseline + spike_delta
                baseline          – median pixel count (the "normal" level)
                stddev            – standard deviation of counts
                total_frames      – how many frames were analysed
                peak_frame_index  – index of the frame with the highest count
        """
        import statistics as _stats

        if lower_hsv is None:
            lower_hsv = [0, 0, 200]
        if upper_hsv is None:
            upper_hsv = [60, 100, 255]

        lower = np.array(lower_hsv, dtype=np.uint8)
        upper = np.array(upper_hsv, dtype=np.uint8)

        ux = zone.get("upper_x", 320)
        uy = zone.get("upper_y", 40)
        lx = zone.get("lower_x", 580)
        ly = zone.get("lower_y", 200)

        roi_w = lx - ux
        roi_h = ly - uy
        roi_total_pixels = roi_w * roi_h if roi_w > 0 and roi_h > 0 else 1

        per_frame_counts: List[int] = []
        peak_count = 0
        peak_frame_index = 0
        debug_masks: List[Optional[np.ndarray]] = []
        debug_rois: List[Optional[np.ndarray]] = []

        try:
            for idx, frame in enumerate(frames):
                # Crop to enemy Pokémon ROI
                roi = frame[uy:ly, ux:lx]
                if roi.size == 0:
                    per_frame_counts.append(0)
                    debug_masks.append(None)
                    debug_rois.append(None)
                    continue

                hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, lower, upper)
                count = int(cv2.countNonZero(mask))
                per_frame_counts.append(count)

                if count > peak_count:
                    peak_count = count
                    peak_frame_index = idx

                # Keep refs for debug saving (only peak + first/last)
                if debug_dir and idx in (0, len(frames) - 1):
                    debug_rois.append(roi.copy())
                    debug_masks.append(mask.copy())
                else:
                    debug_rois.append(None)
                    debug_masks.append(None)

            # ── Compute statistics ────────────────────────────────
            n = len(per_frame_counts)
            if n == 0:
                logger.warning("[BattleSparkle] No frames to analyse")
                return False, {"per_frame_counts": [], "peak_count": 0,
                               "spike_frames": 0, "elevated_frames": 0,
                               "baseline": 0, "stddev": 0,
                               "total_frames": 0, "peak_frame_index": 0}

            baseline = _stats.median(per_frame_counts)
            stddev = _stats.stdev(per_frame_counts) if n > 1 else 0.0
            mean_count = _stats.mean(per_frame_counts)
            min_count = min(per_frame_counts)
            max_count = max(per_frame_counts)

            # Spike delta: at least spike_delta_pct above baseline, but
            # also at least spark_threshold absolute pixels
            spike_delta = max(spark_threshold, baseline * spike_delta_pct)
            elevated_frames = sum(
                1 for c in per_frame_counts if c > baseline + spike_delta
            )

            # Legacy absolute-threshold spike count (for logging/comparison)
            abs_spike_frames = sum(1 for c in per_frame_counts if c >= spark_threshold)

            # ── Decision logic (variance-aware) ───────────────────
            # Primary: require meaningful variance AND elevated frames
            has_variance = stddev > min_variance
            has_elevated = elevated_frames >= min_spike_frames
            # Secondary safety net: absolute peak must still be substantial
            has_peak = peak_count >= peak_threshold

            is_shiny = has_variance and has_elevated and has_peak

            details = {
                "per_frame_counts": per_frame_counts,
                "peak_count": peak_count,
                "spike_frames": abs_spike_frames,
                "elevated_frames": elevated_frames,
                "baseline": round(baseline, 1),
                "stddev": round(stddev, 1),
                "spike_delta": round(spike_delta, 1),
                "total_frames": n,
                "peak_frame_index": peak_frame_index,
                "min_count": min_count,
                "max_count": max_count,
                "mean_count": round(mean_count, 1),
                "roi_total_pixels": roi_total_pixels,
            }

            # ── Enhanced logging ──────────────────────────────────
            logger.info(
                f"[BattleSparkle] ROI=({ux},{uy})->({lx},{ly}) {roi_w}x{roi_h} "
                f"({roi_total_pixels}px) | HSV=[{lower_hsv}]->[{upper_hsv}]"
            )
            logger.info(
                f"[BattleSparkle] counts: min={min_count} max={max_count} "
                f"mean={mean_count:.0f} median={baseline:.0f} stddev={stddev:.1f}"
            )
            logger.info(
                f"[BattleSparkle] peak={peak_count} (frame {peak_frame_index}) | "
                f"abs_spikes={abs_spike_frames}/{n} (thresh={spark_threshold}) | "
                f"elevated={elevated_frames}/{n} (delta={spike_delta:.0f}, "
                f"{spike_delta_pct*100:.0f}% above baseline)"
            )
            logger.info(
                f"[BattleSparkle] variance_ok={has_variance} (stddev={stddev:.1f} "
                f"vs min={min_variance}) | elevated_ok={has_elevated} | "
                f"peak_ok={has_peak} (peak={peak_count} vs thresh={peak_threshold}) "
                f"-> {'SHINY!' if is_shiny else 'normal'}"
            )

            # ── Save debug ROI + mask images ──────────────────────
            if debug_dir:
                self._save_sparkle_debug(
                    debug_dir, encounter_num, frames, per_frame_counts,
                    peak_frame_index, zone, lower, upper, details
                )

            return is_shiny, details

        except Exception as e:
            logger.error(f"Error in battle sparkle detection: {e}")
            return False, {
                "per_frame_counts": per_frame_counts,
                "peak_count": peak_count,
                "spike_frames": 0,
                "elevated_frames": 0,
                "baseline": 0,
                "stddev": 0,
                "total_frames": len(frames),
                "peak_frame_index": 0,
                "error": str(e),
            }

    def _save_sparkle_debug(
        self,
        debug_dir: str,
        encounter_num: int,
        frames: List[np.ndarray],
        per_frame_counts: List[int],
        peak_frame_index: int,
        zone: Dict[str, int],
        lower: np.ndarray,
        upper: np.ndarray,
        details: Dict,
    ):
        """Save debug visualisation images for sparkle detection tuning.

        Saves:
        - The cropped ROI for the peak frame
        - The HSV mask overlay for the peak frame
        - The cropped ROI for the first and last frames
        - A summary text file with per-frame counts and statistics
        """
        from pathlib import Path
        try:
            d = Path(debug_dir)
            d.mkdir(parents=True, exist_ok=True)

            enc = encounter_num
            ux = zone.get("upper_x", 320)
            uy = zone.get("upper_y", 40)
            lx = zone.get("lower_x", 580)
            ly = zone.get("lower_y", 200)

            # Save peak frame ROI + mask
            if peak_frame_index < len(frames):
                peak_frame = frames[peak_frame_index]
                roi = peak_frame[uy:ly, ux:lx]
                if roi.size > 0:
                    cv2.imwrite(str(d / f"enc{enc:04d}_peak_f{peak_frame_index:03d}_roi.png"), roi)
                    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
                    mask = cv2.inRange(hsv, lower, upper)
                    cv2.imwrite(str(d / f"enc{enc:04d}_peak_f{peak_frame_index:03d}_mask.png"), mask)
                    # Overlay: original ROI with mask pixels highlighted in green
                    overlay = roi.copy()
                    overlay[mask > 0] = [0, 255, 0]  # Green highlight
                    blended = cv2.addWeighted(roi, 0.5, overlay, 0.5, 0)
                    cv2.imwrite(str(d / f"enc{enc:04d}_peak_f{peak_frame_index:03d}_overlay.png"), blended)

            # Save first and last frame ROI for comparison
            for label, idx in [("first", 0), ("last", len(frames) - 1)]:
                if 0 <= idx < len(frames):
                    f = frames[idx]
                    roi = f[uy:ly, ux:lx]
                    if roi.size > 0:
                        cv2.imwrite(str(d / f"enc{enc:04d}_{label}_f{idx:03d}_roi.png"), roi)

            # Save summary text file
            summary_path = d / f"enc{enc:04d}_summary.txt"
            with open(summary_path, 'w') as sf:
                sf.write(f"Encounter: {enc}\n")
                sf.write(f"ROI: ({ux},{uy}) -> ({lx},{ly}) = "
                         f"{lx-ux}x{ly-uy} ({details.get('roi_total_pixels',0)}px)\n")
                sf.write(f"Baseline (median): {details.get('baseline',0)}\n")
                sf.write(f"StdDev: {details.get('stddev',0)}\n")
                sf.write(f"Min: {details.get('min_count',0)} Max: {details.get('max_count',0)} "
                         f"Mean: {details.get('mean_count',0)}\n")
                sf.write(f"Peak: {details.get('peak_count',0)} (frame {peak_frame_index})\n")
                sf.write(f"Elevated frames: {details.get('elevated_frames',0)}/{details.get('total_frames',0)}\n")
                sf.write(f"Spike delta: {details.get('spike_delta',0)}\n")
                sf.write(f"\nPer-frame counts:\n")
                for i, c in enumerate(per_frame_counts):
                    marker = " <-- PEAK" if i == peak_frame_index else ""
                    sf.write(f"  frame {i:03d}: {c}{marker}\n")

            logger.info(f"[BattleSparkle] Debug images saved to {d}")

        except Exception as e:
            logger.error(f"[BattleSparkle] Failed to save debug images: {e}")

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
    
    def _fuzzy_match_nature(self, ocr_word: str, language: str = 'en') -> str:
        """
        Fuzzy match an OCR-read word against the list of valid Pokemon natures.
        
        Uses difflib to find the closest match, handling common OCR errors
        like N→H, D→O in the GBA pixel font.
        
        When language='fr', matches against French nature names and returns
        the English equivalent for normalized DB storage.
        
        Args:
            ocr_word: The word read by OCR (e.g., 'HAUGHTY', 'BOLO', 'TIMIDE')
            language: Game language ('en' or 'fr')
        
        Returns:
            English nature name (capitalized, e.g., 'Naughty') or 'Unknown'
        """
        word_upper = ocr_word.upper().strip()
        
        if language == 'fr':
            # ── French matching: match against French natures, return English ──
            # 1. Exact match against French uppercase
            if word_upper in FRENCH_UPPER_TO_ENGLISH:
                return FRENCH_UPPER_TO_ENGLISH[word_upper]
            
            # 2. Fuzzy match against French natures (handles OCR mangling accents)
            matches = difflib.get_close_matches(
                word_upper, FRENCH_NATURES_UPPER, n=1, cutoff=0.6
            )
            if matches:
                english = FRENCH_UPPER_TO_ENGLISH[matches[0]]
                logger.info(f"OCR fuzzy matched (fr) '{ocr_word}' -> '{english}'")
                return english
            
            # 3. Fall through to English matching (some natures are identical)
        
        # ── English matching (default) ──
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
        then extracts the nature word. Supports both English and French:
          - English: "NAUGHTY nature." → word BEFORE 'nature'
          - French:  "de nature TIMIDE." → word AFTER 'nature'
        
        Always returns the English nature name for normalized DB storage.
        
        Args:
            color_frame: Color frame (BGR format) of the summary screen
        
        Returns:
            English nature name (capitalized, e.g., 'Naughty') or 'Unknown'
        """
        if self.ocr_engine is False:
            logger.warning("[Nature] OCR engine not available — returning Unknown")
            return 'Unknown'
        
        try:
            # Get game language and nature text zone coordinates from config
            lang = settings.game_language
            nz = settings.nature_text_zone
            ux = nz.get('upper_x', 0)
            uy = nz.get('upper_y', 300)
            lx = nz.get('lower_x', 350)
            ly = nz.get('lower_y', 380)
            
            h, w = color_frame.shape[:2]
            logger.info(
                f"[Nature] Frame size: {w}x{h} | "
                f"Zone: ({ux},{uy})->({lx},{ly}) | "
                f"crop_mode={settings.crop_mode} | lang={lang}"
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
            
            # ── Choose regex pattern based on game language ──
            if lang == 'fr':
                # French: "de nature TIMIDE." → nature word comes AFTER 'nature'
                match = re.search(r'nature\s+(\w+)', full_text, re.IGNORECASE | re.UNICODE)
            else:
                # English: "NAUGHTY nature." → nature word comes BEFORE 'nature'
                match = re.search(r'(\w+)\s+nature', full_text, re.IGNORECASE)
            
            if match:
                nature_word = match.group(1)
                matched_nature = self._fuzzy_match_nature(nature_word, lang)
                logger.info(f"[Nature] Regex matched word='{nature_word}' -> '{matched_nature}'")
                if matched_nature == 'Unknown':
                    self._save_nature_debug(
                        roi, scaled, f'fuzzy_fail_regex (word={nature_word}, lang={lang})',
                        result, full_text
                    )
                return matched_nature
            
            # Fallback: find the text adjacent to the "nature" entry
            # Sometimes OCR splits them into separate entries
            for i, item in enumerate(result):
                text = item[1].strip().lower()
                if text == 'nature' or text == 'nature.':
                    if lang == 'fr':
                        # French: nature word comes AFTER 'nature'
                        if i < len(result) - 1:
                            nature_word = result[i + 1][1]
                            # Strip trailing period if present
                            nature_word = nature_word.rstrip('.')
                            matched_nature = self._fuzzy_match_nature(nature_word, lang)
                            logger.info(
                                f"[Nature] Fallback (fr) matched word='{nature_word}' -> '{matched_nature}'"
                            )
                            if matched_nature == 'Unknown':
                                self._save_nature_debug(
                                    roi, scaled,
                                    f'fuzzy_fail_fallback_fr (word={nature_word})',
                                    result, full_text
                                )
                            return matched_nature
                    else:
                        # English: nature word comes BEFORE 'nature'
                        if i > 0:
                            nature_word = result[i - 1][1]
                            matched_nature = self._fuzzy_match_nature(nature_word, lang)
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
