# Egg Yolk Color Scorer

Estimates DSM Yolk Color Fan score (1–15) from a photo of a cracked egg on a standard white plate.

## How it works

1. **White-balance correction** — Detects the white plate and uses it as a color reference to normalize lighting.
2. **Yolk segmentation** — HSV color masking isolates the yolk from the plate and egg white.
3. **Color extraction** — K-means clustering on yolk pixels finds the dominant color.
4. **Lab\* matching** — Converts to CIE L\*a\*b\* color space and computes Delta-E (CIE2000) against all 15 DSM reference colors.
5. **Score output** — Reports the best match, confidence level, and nearest alternatives.

## Setup

```bash
# Python 3.9+
pip install -r requirements.txt
```

## Usage

### Score a single image

```bash
python yolk_scorer.py path/to/egg_photo.jpg
```

With debug output (saves intermediate images):

```bash
python yolk_scorer.py path/to/egg_photo.jpg --debug
```

### Generate synthetic test images

```bash
python generate_test_images.py
```

This creates test images in `test_images/` with known yolk colors for validation.

### Batch scoring

```bash
python batch_score.py test_images/
python batch_score.py test_images/ --csv results.csv
```

## Quick start (full pipeline)

```bash
pip install -r requirements.txt
python generate_test_images.py
python batch_score.py test_images/
python yolk_scorer.py test_images/synthetic_yolk_score_7.jpg --debug
```

## Project structure

```
devenish-yolk-scorer/
├── yolk_scorer.py           # Core scoring pipeline
├── reference_colors.py      # DSM Yolk Color Fan L*a*b* reference values
├── generate_test_images.py  # Synthetic test image generator
├── batch_score.py           # Batch scoring + CSV export
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── test_images/             # Generated/real test images
```

## Technical decisions

- **Lab\* over RGB/HSV for matching**: Lab\* is perceptually uniform — equal distances correspond to equal perceived color differences. The DSM color fan is defined in this space.
- **Delta-E CIE2000 over Euclidean**: CIE2000 accounts for human perception non-linearities, especially in the yellow-orange range where yolk colors live.
- **White plate as calibration**: The "standard plate" requirement in the spec doubles as a white-balance reference — elegant because it requires no extra calibration hardware.
- **K-means over simple mean**: Handles yolks with slight color variation, highlights, or surface texture without averaging in non-representative pixels.
- **No ML model required**: Color-space matching against a known reference table works for a prototype and requires zero training data. A production build could layer a fine-tuned model on top.

## Limitations

- Synthetic test images validate the pipeline logic but not real-world robustness.
- White balance depends on having enough visible plate area.
- Extreme lighting (very warm/cool) may push corrections beyond the safety clamp.
- Camera-specific color science (HDR, night mode) is not accounted for.
