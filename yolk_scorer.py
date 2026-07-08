"""
Egg Yolk Color Scorer
=====================
Estimates DSM Yolk Color Fan score (1-15) from a photo of a cracked egg
on a standard white plate.

Pipeline:
  1. Detect white plate for white-balance correction
  2. Segment the yolk using HSV color masking
  3. Extract dominant yolk color via k-means clustering
  4. Convert to CIE L*a*b* color space
  5. Match against DSM reference colors using Delta-E (CIE2000)
  6. Output score + confidence

Usage:
  python yolk_scorer.py <image_path>
  python yolk_scorer.py <image_path> --debug   # saves intermediate images
"""

import sys
import argparse
import os
import numpy as np
import cv2
from pathlib import Path

from reference_colors import DSM_YOLK_LAB


# ---------------------------------------------------------------------------
# Delta-E CIE2000 implementation
# ---------------------------------------------------------------------------

def delta_e_cie2000(lab1, lab2, kL=1, kC=1, kH=1):
    """
    Compute Delta-E 2000 between two L*a*b* colors.
    More perceptually uniform than simple Euclidean distance in Lab.
    """
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    # Step 1: Calculate C' and h'
    C1 = np.sqrt(a1**2 + b1**2)
    C2 = np.sqrt(a2**2 + b2**2)
    C_avg = (C1 + C2) / 2.0

    G = 0.5 * (1 - np.sqrt(C_avg**7 / (C_avg**7 + 25**7)))

    a1_prime = a1 * (1 + G)
    a2_prime = a2 * (1 + G)

    C1_prime = np.sqrt(a1_prime**2 + b1**2)
    C2_prime = np.sqrt(a2_prime**2 + b2**2)

    h1_prime = np.degrees(np.arctan2(b1, a1_prime)) % 360
    h2_prime = np.degrees(np.arctan2(b2, a2_prime)) % 360

    # Step 2: Calculate delta values
    dL_prime = L2 - L1
    dC_prime = C2_prime - C1_prime

    if C1_prime * C2_prime == 0:
        dh_prime = 0
    elif abs(h2_prime - h1_prime) <= 180:
        dh_prime = h2_prime - h1_prime
    elif h2_prime - h1_prime > 180:
        dh_prime = h2_prime - h1_prime - 360
    else:
        dh_prime = h2_prime - h1_prime + 360

    dH_prime = 2 * np.sqrt(C1_prime * C2_prime) * np.sin(np.radians(dh_prime / 2))

    # Step 3: Calculate CIEDE2000
    L_avg_prime = (L1 + L2) / 2.0
    C_avg_prime = (C1_prime + C2_prime) / 2.0

    if C1_prime * C2_prime == 0:
        h_avg_prime = h1_prime + h2_prime
    elif abs(h1_prime - h2_prime) <= 180:
        h_avg_prime = (h1_prime + h2_prime) / 2.0
    elif h1_prime + h2_prime < 360:
        h_avg_prime = (h1_prime + h2_prime + 360) / 2.0
    else:
        h_avg_prime = (h1_prime + h2_prime - 360) / 2.0

    T = (1
         - 0.17 * np.cos(np.radians(h_avg_prime - 30))
         + 0.24 * np.cos(np.radians(2 * h_avg_prime))
         + 0.32 * np.cos(np.radians(3 * h_avg_prime + 6))
         - 0.20 * np.cos(np.radians(4 * h_avg_prime - 63)))

    SL = 1 + 0.015 * (L_avg_prime - 50)**2 / np.sqrt(20 + (L_avg_prime - 50)**2)
    SC = 1 + 0.045 * C_avg_prime
    SH = 1 + 0.015 * C_avg_prime * T

    RT_term = -np.sin(2 * np.radians(60 * np.exp(-((h_avg_prime - 275) / 25)**2)))
    RC = 2 * np.sqrt(C_avg_prime**7 / (C_avg_prime**7 + 25**7))
    RT = RT_term * RC

    dE = np.sqrt(
        (dL_prime / (kL * SL))**2
        + (dC_prime / (kC * SC))**2
        + (dH_prime / (kH * SH))**2
        + RT * (dC_prime / (kC * SC)) * (dH_prime / (kH * SH))
    )
    return dE


# ---------------------------------------------------------------------------
# White balance correction using the plate
# ---------------------------------------------------------------------------

def white_balance_plate(image):
    """
    Correct white balance by using the white plate as a reference.
    Detects the plate (largest bright region), samples its color,
    and scales channels so the plate reads as neutral white.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Threshold for bright regions (the plate)
    _, bright_mask = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

    # Clean up with morphological operations
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel)
    bright_mask = cv2.morphologyEx(bright_mask, cv2.MORPH_OPEN, kernel)

    # Find the largest contour (should be the plate)
    contours, _ = cv2.findContours(bright_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return image  # fallback: no plate detected

    plate_contour = max(contours, key=cv2.contourArea)
    plate_mask = np.zeros_like(gray)
    cv2.drawContours(plate_mask, [plate_contour], -1, 255, -1)

    # Erode the plate mask to avoid edges and the egg itself
    erode_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (40, 40))
    plate_edge_mask = cv2.erode(plate_mask, erode_kernel)

    # Exclude the yolk/egg area from the plate sample
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    egg_mask = cv2.inRange(hsv, (10, 40, 100), (40, 255, 255))
    egg_mask_dilated = cv2.dilate(egg_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (50, 50)))
    plate_sample_mask = cv2.bitwise_and(plate_edge_mask, cv2.bitwise_not(egg_mask_dilated))

    if cv2.countNonZero(plate_sample_mask) < 100:
        return image  # fallback: not enough plate pixels

    # Sample the plate color
    plate_pixels = image[plate_sample_mask > 0]
    plate_mean = plate_pixels.mean(axis=0)  # BGR

    # Scale so plate reads as (255, 255, 255) -- but cap to avoid overflow
    target_white = 240.0  # slightly below 255 to avoid clipping
    scale = target_white / (plate_mean + 1e-6)
    scale = np.clip(scale, 0.5, 2.0)  # safety clamp

    corrected = image.astype(np.float32) * scale[np.newaxis, np.newaxis, :]
    corrected = np.clip(corrected, 0, 255).astype(np.uint8)

    return corrected


# ---------------------------------------------------------------------------
# Yolk segmentation
# ---------------------------------------------------------------------------

def segment_yolk(image, debug_dir=None):
    """
    Segment the egg yolk from the image using HSV color thresholding.
    Returns the yolk mask and the bounding circle of the yolk.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Yolk color range in HSV: yellow to orange
    # H: 10-35 (yellow-orange), S: 80-255 (saturated), V: 100-255 (bright)
    lower_yolk = np.array([10, 80, 100])
    upper_yolk = np.array([38, 255, 255])
    mask = cv2.inRange(hsv, lower_yolk, upper_yolk)

    # Extend to catch deeper orange yolks (scores 11-15)
    lower_deep = np.array([0, 100, 100])
    upper_deep = np.array([12, 255, 255])
    mask_deep = cv2.inRange(hsv, lower_deep, upper_deep)
    mask = cv2.bitwise_or(mask, mask_deep)

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=3)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)

    # Find the largest blob (the yolk)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None, None

    yolk_contour = max(contours, key=cv2.contourArea)
    min_area = image.shape[0] * image.shape[1] * 0.005  # at least 0.5% of image
    if cv2.contourArea(yolk_contour) < min_area:
        return None, None

    # Create clean yolk mask from the largest contour only
    yolk_mask = np.zeros_like(mask)
    cv2.drawContours(yolk_mask, [yolk_contour], -1, 255, -1)

    # Erode to get the inner region (avoid edge contamination from egg white)
    erode_size = max(5, int(np.sqrt(cv2.contourArea(yolk_contour)) * 0.1))
    erode_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode_size, erode_size))
    yolk_inner = cv2.erode(yolk_mask, erode_kernel)

    # Fallback if erosion removes everything
    if cv2.countNonZero(yolk_inner) < 50:
        yolk_inner = yolk_mask

    if debug_dir:
        debug_overlay = image.copy()
        debug_overlay[yolk_inner > 0] = (0, 255, 0)
        blended = cv2.addWeighted(image, 0.7, debug_overlay, 0.3, 0)
        cv2.imwrite(os.path.join(debug_dir, "03_yolk_segmentation.jpg"), blended)
        cv2.imwrite(os.path.join(debug_dir, "03b_yolk_mask.jpg"), yolk_inner)

    return yolk_inner, yolk_contour


# ---------------------------------------------------------------------------
# Dominant color extraction
# ---------------------------------------------------------------------------

def extract_dominant_color(image, mask, n_clusters=3):
    """
    Extract the dominant color from the masked yolk region using k-means.
    Returns the dominant color in BGR.
    """
    pixels = image[mask > 0].reshape(-1, 3).astype(np.float32)

    if len(pixels) < 10:
        return None

    # k-means clustering to find dominant colors
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    k = min(n_clusters, len(pixels))
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 5, cv2.KMEANS_PP_CENTERS)

    # Pick the cluster with the most pixels
    label_counts = np.bincount(labels.flatten())
    dominant_idx = np.argmax(label_counts)
    dominant_bgr = centers[dominant_idx]

    return dominant_bgr


# ---------------------------------------------------------------------------
# Color matching
# ---------------------------------------------------------------------------

def bgr_to_lab(bgr_color):
    """Convert a single BGR color to CIE L*a*b*."""
    pixel = np.uint8([[bgr_color]])
    lab_pixel = cv2.cvtColor(pixel, cv2.COLOR_BGR2LAB)
    L, a, b = lab_pixel[0, 0].astype(np.float64)
    # OpenCV Lab ranges: L [0,255], a [0,255], b [0,255]
    # Convert to standard Lab: L [0,100], a [-128,127], b [-128,127]
    L = L * 100.0 / 255.0
    a = a - 128.0
    b = b - 128.0
    return (L, a, b)


def match_yolk_score(lab_color):
    """
    Match a Lab color against the DSM reference table.
    Returns (score, delta_e, all_distances).
    """
    distances = {}
    for score, ref_lab in DSM_YOLK_LAB.items():
        de = delta_e_cie2000(lab_color, ref_lab)
        distances[score] = de

    best_score = min(distances, key=distances.get)
    best_de = distances[best_score]

    return best_score, best_de, distances


# ---------------------------------------------------------------------------
# Confidence estimation
# ---------------------------------------------------------------------------

def compute_confidence(best_de, distances):
    """
    Estimate confidence based on how clearly the best match stands out.
    Low delta-E = good match. Large gap to second-best = clear winner.
    """
    sorted_dists = sorted(distances.values())

    # Base confidence from absolute match quality
    if best_de < 3:
        base = 0.95
    elif best_de < 6:
        base = 0.85
    elif best_de < 10:
        base = 0.70
    elif best_de < 15:
        base = 0.50
    else:
        base = 0.30

    # Bonus for separation from second-best match
    if len(sorted_dists) > 1:
        gap = sorted_dists[1] - sorted_dists[0]
        separation_bonus = min(0.1, gap * 0.02)
        base = min(0.99, base + separation_bonus)

    return round(base, 2)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def score_yolk(image_path, debug=False):
    """
    Full pipeline: load image -> white balance -> segment -> extract color -> match.
    Returns a result dict.
    """
    image = cv2.imread(str(image_path))
    if image is None:
        return {"error": f"Could not load image: {image_path}"}

    debug_dir = None
    if debug:
        debug_dir = os.path.join(os.path.dirname(image_path), "debug_output")
        os.makedirs(debug_dir, exist_ok=True)
        cv2.imwrite(os.path.join(debug_dir, "01_original.jpg"), image)

    # Step 1: White balance
    corrected = white_balance_plate(image)
    if debug_dir:
        cv2.imwrite(os.path.join(debug_dir, "02_white_balanced.jpg"), corrected)

    # Step 2: Segment yolk
    yolk_mask, yolk_contour = segment_yolk(corrected, debug_dir)
    if yolk_mask is None:
        return {"error": "Could not detect yolk in image. Ensure the egg is cracked on a white plate."}

    yolk_pixel_count = cv2.countNonZero(yolk_mask)

    # Step 3: Extract dominant color
    dominant_bgr = extract_dominant_color(corrected, yolk_mask)
    if dominant_bgr is None:
        return {"error": "Could not extract yolk color."}

    # Step 4: Convert to Lab
    lab_color = bgr_to_lab(dominant_bgr)

    # Step 5: Match against DSM reference
    score, best_de, all_distances = match_yolk_score(lab_color)
    confidence = compute_confidence(best_de, all_distances)

    # Nearest alternatives
    sorted_scores = sorted(all_distances.items(), key=lambda x: x[1])
    top_3 = sorted_scores[:3]

    result = {
        "score": score,
        "confidence": confidence,
        "delta_e": round(best_de, 2),
        "extracted_lab": tuple(round(v, 1) for v in lab_color),
        "extracted_bgr": tuple(int(v) for v in dominant_bgr),
        "reference_lab": DSM_YOLK_LAB[score],
        "yolk_pixels": yolk_pixel_count,
        "alternatives": [(s, round(d, 2)) for s, d in top_3],
    }

    if debug_dir:
        _save_debug_result(corrected, yolk_mask, dominant_bgr, result, debug_dir)

    return result


def _save_debug_result(image, mask, dominant_bgr, result, debug_dir):
    """Save a visual debug summary."""
    h, w = image.shape[:2]
    canvas = np.zeros((h, w + 200, 3), dtype=np.uint8)
    canvas[:h, :w] = image

    # Draw yolk outline
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(canvas, contours, -1, (0, 255, 0), 2)

    # Color swatch sidebar
    sidebar_x = w + 10
    # Extracted color
    cv2.rectangle(canvas, (sidebar_x, 10), (sidebar_x + 80, 50),
                  tuple(int(v) for v in dominant_bgr), -1)
    cv2.putText(canvas, "Extracted", (sidebar_x, 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # Reference color
    from reference_colors import DSM_YOLK_RGB
    ref_rgb = DSM_YOLK_RGB[result["score"]]
    ref_bgr = (ref_rgb[2], ref_rgb[1], ref_rgb[0])
    cv2.rectangle(canvas, (sidebar_x, 90), (sidebar_x + 80, 130), ref_bgr, -1)
    cv2.putText(canvas, f"DSM {result['score']}", (sidebar_x, 150),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # Score text
    cv2.putText(canvas, f"Score: {result['score']}", (sidebar_x, 185),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.putText(canvas, f"Conf: {result['confidence']}", (sidebar_x, 210),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    cv2.putText(canvas, f"dE: {result['delta_e']}", (sidebar_x, 235),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

    cv2.imwrite(os.path.join(debug_dir, "04_result_summary.jpg"), canvas)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_result(result):
    """Pretty-print the scoring result."""
    if "error" in result:
        print(f"\n  ERROR: {result['error']}")
        return

    score = result["score"]
    conf = result["confidence"]
    de = result["delta_e"]
    lab = result["extracted_lab"]
    alts = result["alternatives"]

    # Score descriptor
    if score <= 5:
        desc = "Pale"
    elif score <= 10:
        desc = "Medium"
    else:
        desc = "Dark"

    conf_desc = "High" if conf >= 0.80 else "Medium" if conf >= 0.60 else "Low"

    print(f"""
  +======================================+
  |   EGG YOLK COLOR SCORE               |
  +======================================+
  |                                       |
  |   Score:      {score:<2} / 15  ({desc:<6})       |
  |   Confidence: {conf:.0%}  ({conf_desc:<6})       |
  |   Delta-E:    {de:<6}                  |
  |                                       |
  +--------------------------------------+
  |   Extracted L*a*b*: {lab[0]:>5.1f}, {lab[1]:>5.1f}, {lab[2]:>5.1f}   |
  |   Reference  L*a*b*: {result['reference_lab'][0]:>5.1f}, {result['reference_lab'][1]:>5.1f}, {result['reference_lab'][2]:>5.1f}  |
  |   Yolk pixels: {result['yolk_pixels']:,}               |
  +--------------------------------------+
  |   Nearest matches:                    |""")
    for s, d in alts:
        marker = " <--" if s == score else ""
        print(f"  |     Score {s:>2}: Delta-E = {d:<6}{marker:>8}  |")
    print(f"""  |                                       |
  +======================================+
""")


def main():
    parser = argparse.ArgumentParser(
        description="Estimate egg yolk color score (1-15) from a photo."
    )
    parser.add_argument("image", help="Path to egg photo")
    parser.add_argument("--debug", action="store_true",
                        help="Save intermediate debug images")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: File not found: {image_path}")
        sys.exit(1)

    print(f"  Analyzing: {image_path.name}")
    result = score_yolk(str(image_path), debug=args.debug)
    print_result(result)

    if args.debug and "error" not in result:
        debug_dir = os.path.join(os.path.dirname(str(image_path)), "debug_output")
        print(f"  Debug images saved to: {debug_dir}/")


if __name__ == "__main__":
    main()
