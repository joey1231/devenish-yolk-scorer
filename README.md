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

## Testing with included images

The repo ships with both synthetic and real egg photos in `test_images/`.

### Synthetic test images (known ground truth)

```bash
# Score a mid-range yellow yolk (expected: ~7-8)
python yolk_scorer.py test_images/synthetic_yolk_score_7.jpg

# Score a pale yolk (expected: ~1-2)
python yolk_scorer.py test_images/synthetic_yolk_score_1.jpg

# Score a deep orange yolk (expected: ~13-15)
python yolk_scorer.py test_images/synthetic_yolk_score_13.jpg
```

### Real egg photos

```bash
# Single yolk on blue surface -- tests scoring without a white plate
python yolk_scorer.py test_images/real_egg_yolk_1.jpg --debug

# Two eggs cracked into a white bowl -- tests white-balance + multi-yolk
python yolk_scorer.py test_images/real_egg_yolk_2.jpg --debug

# Multiple yolks in eggshell halves -- tests circularity filter
python yolk_scorer.py test_images/real_egg_yolk_3.jpg --debug
```

### Test with your own photo

```bash
# Take a photo of a cracked egg on a white plate, then:
python yolk_scorer.py path/to/your_egg.jpg --debug
```

The `--debug` flag saves intermediate images to `test_images/debug_output/`:
- `01_original.jpg` -- Input image
- `02_white_balanced.jpg` -- After white-balance correction
- `03_yolk_segmentation.jpg` -- Yolk mask overlay (green = detected yolk)
- `03b_yolk_mask.jpg` -- Binary yolk mask
- `04_result_summary.jpg` -- Annotated result with color swatches

### Batch scoring + CSV export

```bash
# Score all images and print a table
python batch_score.py test_images/

# Same, but also save results to CSV
python batch_score.py test_images/ --csv results.csv
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
├── PART2_ANSWERS.md         # Part 2 written answers
├── results.csv              # Batch scoring results
└── test_images/             # Synthetic + real test images
    ├── synthetic_yolk_score_*.jpg
    ├── real_egg_yolk_*.jpg
    └── debug_output/        # Debug visualizations
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
