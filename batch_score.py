"""
Batch scoring: run the yolk scorer across all images in a directory
and output a results table. Useful for validation testing.

Usage:
  python batch_score.py test_images/
  python batch_score.py test_images/ --csv results.csv
"""

import argparse
import csv
import os
import sys
from pathlib import Path
from yolk_scorer import score_yolk


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}


def batch_score(image_dir, csv_path=None):
    image_dir = Path(image_dir)
    if not image_dir.is_dir():
        print(f"Error: {image_dir} is not a directory")
        sys.exit(1)

    images = sorted(
        f for f in image_dir.iterdir()
        if f.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not images:
        print(f"No images found in {image_dir}")
        sys.exit(1)

    results = []
    print(f"\n  Scoring {len(images)} images in {image_dir}/\n")
    print(f"  {'Image':<45} {'Score':>5} {'Conf':>6} {'Delta-E':>8} {'L*':>6} {'a*':>6} {'b*':>6}")
    print(f"  {'-' * 45} {'-' * 5} {'-' * 6} {'-' * 8} {'-' * 6} {'-' * 6} {'-' * 6}")

    for img_path in images:
        result = score_yolk(str(img_path))

        if "error" in result:
            print(f"  {img_path.name:<45} ERROR: {result['error']}")
            results.append({"image": img_path.name, "error": result["error"]})
            continue

        lab = result["extracted_lab"]
        print(f"  {img_path.name:<45} {result['score']:>5} {result['confidence']:>5.0%} {result['delta_e']:>8.2f} {lab[0]:>6.1f} {lab[1]:>6.1f} {lab[2]:>6.1f}")

        results.append({
            "image": img_path.name,
            "score": result["score"],
            "confidence": result["confidence"],
            "delta_e": result["delta_e"],
            "L": lab[0],
            "a": lab[1],
            "b": lab[2],
        })

    # Summary
    valid = [r for r in results if "error" not in r]
    if valid:
        avg_conf = sum(r["confidence"] for r in valid) / len(valid)
        avg_de = sum(r["delta_e"] for r in valid) / len(valid)
        scores = [r["score"] for r in valid]
        print(f"\n  Summary: {len(valid)} scored, {len(results) - len(valid)} errors")
        print(f"  Score range: {min(scores)} - {max(scores)}")
        print(f"  Avg confidence: {avg_conf:.0%}")
        print(f"  Avg Delta-E: {avg_de:.2f}")

    # Optional CSV export
    if csv_path and valid:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["image", "score", "confidence", "delta_e", "L", "a", "b"])
            writer.writeheader()
            writer.writerows(valid)
        print(f"\n  Results saved to {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="Batch score egg yolk images")
    parser.add_argument("directory", help="Directory containing egg images")
    parser.add_argument("--csv", help="Export results to CSV file")
    args = parser.parse_args()

    batch_score(args.directory, args.csv)


if __name__ == "__main__":
    main()
