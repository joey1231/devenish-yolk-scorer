"""
Generate synthetic test images of eggs on white plates.

Since we don't have real egg photos, this generates clean synthetic images
with known yolk colors so we can validate the pipeline end-to-end.
Each image has a white circular plate, translucent egg white, and a
colored yolk matching a specific DSM score.
"""

import numpy as np
import cv2
import os
from reference_colors import DSM_YOLK_RGB


def generate_egg_image(yolk_score, output_path, plate_diameter=500):
    """Generate a synthetic egg photo for a given DSM yolk score."""
    size = plate_diameter + 200
    img = np.full((size, size, 3), (60, 60, 60), dtype=np.uint8)  # dark background

    center = (size // 2, size // 2)
    plate_r = plate_diameter // 2

    # Draw white plate
    cv2.circle(img, center, plate_r, (245, 245, 240), -1)
    # Subtle plate rim shadow
    cv2.circle(img, center, plate_r, (200, 200, 195), 3)

    # Draw egg white (translucent, irregular blob)
    white_r = int(plate_r * 0.55)
    egg_center = (center[0] + np.random.randint(-20, 20),
                  center[1] + np.random.randint(-20, 20))

    # Create irregular egg white shape
    pts = []
    for angle in np.linspace(0, 2 * np.pi, 60):
        r = white_r + np.random.randint(-30, 30)
        x = int(egg_center[0] + r * np.cos(angle))
        y = int(egg_center[1] + r * np.sin(angle))
        pts.append([x, y])
    pts = np.array(pts, dtype=np.int32)

    # Semi-transparent egg white
    overlay = img.copy()
    cv2.fillPoly(overlay, [pts], (240, 240, 235))
    cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)

    # Draw yolk
    yolk_r = int(plate_r * 0.22)
    yolk_rgb = DSM_YOLK_RGB[yolk_score]
    yolk_bgr = (yolk_rgb[2], yolk_rgb[1], yolk_rgb[0])

    # Yolk with slight gradient (darker at edges)
    for i in range(yolk_r, 0, -1):
        t = i / yolk_r
        # Darken toward center slightly for realism
        factor = 0.85 + 0.15 * t
        color = tuple(int(c * factor) for c in yolk_bgr)
        cv2.circle(img, egg_center, i, color, -1)

    # Small highlight on yolk
    highlight_pos = (egg_center[0] - yolk_r // 3, egg_center[1] - yolk_r // 3)
    highlight_overlay = img.copy()
    cv2.circle(highlight_overlay, highlight_pos, yolk_r // 5, (255, 255, 255), -1)
    cv2.addWeighted(highlight_overlay, 0.15, img, 0.85, 0, img)

    cv2.imwrite(output_path, img)
    return output_path


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "test_images")
    os.makedirs(output_dir, exist_ok=True)

    # Generate test images for a spread of scores
    test_scores = [1, 3, 5, 7, 9, 11, 13, 15]

    np.random.seed(42)  # reproducible

    print("Generating synthetic test images...")
    for score in test_scores:
        path = os.path.join(output_dir, f"synthetic_yolk_score_{score}.jpg")
        generate_egg_image(score, path)
        print(f"  Score {score:>2}: {path}")

    print(f"\nGenerated {len(test_scores)} test images in {output_dir}/")
    print("Run: python yolk_scorer.py test_images/synthetic_yolk_score_7.jpg --debug")


if __name__ == "__main__":
    main()
