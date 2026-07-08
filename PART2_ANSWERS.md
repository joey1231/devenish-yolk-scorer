# Part 2 — Answers

## 1. Walk us through your thinking — Why did you scope Part 1 the way you did? What alternatives did you consider and reject, and why?

I chose a deterministic color-space matching approach over machine learning because the constraints pointed that way:

**What I built:** A pipeline that white-balances using the plate, segments the yolk with HSV masking, extracts the dominant color via k-means, converts to CIE L*a*b*, and matches against the 15 DSM reference colors using Delta-E CIE2000.

**Why this approach:**
- The DSM Yolk Color Fan already defines exact color targets. This is a matching problem, not a classification problem. I don't need a model to learn what a "score 8" looks like — the standard tells me.
- Zero training data required. I don't have labeled egg photos, and collecting them is a project in itself.
- Fully interpretable. I can show exactly which pixels drove the score and why score 8 beat score 9 (Delta-E of 2.34 vs 4.15). This matters for building trust with users who currently rely on physical color fans.
- Runs locally. No API calls, no network dependency, no per-inference cost. Critical for a phone tool used in barns with spotty signal.

**What I rejected:**

- **Vision LLM (GPT-4V / Claude):** Fast to prototype, but can't run on a phone, costs per-call, and returns subjective estimates that can't be traced back to the DSM standard. Good for a 30-minute demo, wrong for a tool people rely on.
- **CNN with transfer learning (ResNet/EfficientNet fine-tuned on yolk images):** This is the right production approach if you have 500+ labeled images across the full 1-15 range. I don't have that data, and generating synthetic training data would just teach the model my own assumptions about what each score looks like. Rejected for the prototype, but I'd recommend it for the real build.
- **Simple RGB averaging:** Too naive. RGB distance doesn't correlate with perceptual color difference. A yolk that's (255, 160, 0) and one that's (255, 140, 0) look nearly identical to the eye but are 20 units apart in RGB. Lab* with Delta-E CIE2000 solves this.

**The one insight that shaped the architecture:** The problem statement says "standard plate" and underlines "standard." That's a built-in white-balance reference. The plate is effectively a free color calibration card. Once I recognized that, the pipeline fell into place — white-balance off the plate, segment the yolk, match in Lab*.

---

## 2. If we decided to build this for real, what would the hardest challenges be?

**Lighting normalization is the hardest problem by far.** The prototype uses the white plate for white balance, and that works under reasonable conditions. But real-world use means:

- Mixed lighting (daylight from a window + warm overhead bulbs)
- Shadows cast by the phone itself
- Fluorescent lighting in production facilities that shifts color temperature
- Users who ignore the "white plate" instruction and use whatever surface is nearby

The plate-based correction handles single-source lighting well. Mixed lighting or colored surfaces would need either a physical color reference card (like the X-Rite ColorChecker placed next to the egg) or a more sophisticated computational approach — possibly estimating illuminant from multiple reference points in the scene.

**Camera variation is the second hardest.** Every phone applies its own color processing — auto-HDR, computational photography, night mode, vendor-specific tuning. An iPhone and a Samsung will render the same yolk differently. Solutions: either raw camera capture (most phones support it but it's buried in APIs), or a device-specific calibration step where the user photographs the physical DSM color fan once and we compute a per-device correction profile.

**Ground truth collection is the third.** To validate accuracy, you need hundreds of eggs scored by trained human graders using the physical DSM color fan, under controlled lighting, with photos taken on multiple phone models. Human inter-rater reliability on the DSM scale is about +-1 point — that's our accuracy ceiling. Collecting this dataset isn't technically hard, but it's logistically expensive and requires access to eggs across the full 1-15 range (scores below 3 and above 13 are rare in commercial production).

**Edge cases in yolk appearance:** Double yolks, blood spots, broken yolks bleeding into the white, very fresh eggs with thick albumen that optically distorts the yolk color when viewed through it, yolks with color gradients (darker ring at the edge, lighter center).

---

## 3. How would you verify the accuracy of the app? What would you measure and what accuracy threshold would you consider acceptable to ship?

**What to measure:**

- **Mean Absolute Error (MAE):** Average difference between predicted score and expert-graded ground truth, in DSM scale points. This is the primary metric.
- **Within-1 accuracy:** Percentage of predictions within +-1 point of the expert score. This is the metric that matters most for shipping, because even trained human graders disagree by +-1 on the same egg.
- **Confusion matrix across bands:** Pale (1-5), Medium (6-10), Dark (11-15). A prediction of 6 when the true score is 7 is a rounding error. A prediction of 6 when the true score is 12 is a failure. The confusion matrix catches systematic mis-classification across bands.
- **Max error:** The largest single prediction error. Even one prediction off by 5+ points would undermine user trust.

**Validation protocol:**

1. Collect 200+ eggs spanning the full 1-15 range (oversample rare scores at the extremes).
2. Each egg scored by 2+ trained graders using the physical DSM color fan under controlled D65 lighting (the standard illuminant for color assessment).
3. Each egg photographed on 3+ phone models (iPhone, Samsung, Pixel) under 2+ lighting conditions (controlled lab light, typical indoor).
4. Test set is held out — never seen during development or calibration.
5. Evaluate independently per phone model and lighting condition, not just in aggregate.

**Acceptable thresholds to ship:**

- MAE <= 1.0 (average prediction within 1 point of expert consensus)
- Within-1 accuracy >= 85%
- Zero predictions off by more than 3 points
- Stratified performance: accuracy holds across pale, medium, and dark bands — not just averaging well because mid-range scores are easy

**Why these thresholds:** The tool replaces human visual comparison against a physical color fan. Human inter-rater reliability is about +-1 point. If the app matches that, it's as good as a trained grader. If it's consistently within +-1 with no catastrophic misses, users can trust it for feed evaluation decisions.

I'd also track accuracy drift over time — as phone manufacturers update their camera software, color rendering changes. A quarterly recalibration check with a standard test set would catch this.

---

## 4. What you'd want to know before signing up to build this for real — What questions would you ask us before quoting a budget or timeline?

**Product scope:**

- Is this a standalone app or a feature inside an existing Devenish platform?
- iOS only, Android only, or both?
- Does it need to work offline? (Field use in barns with no signal.)
- Who is the primary user? Farmers, feed sales reps, lab technicians, QA inspectors? Their technical comfort level and use environment differ significantly.
- Is this a sales tool (demonstrating feed efficacy to customers), a QA tool (internal quality checks), or both?

**Data and accuracy:**

- Do you have labeled training data — photos of eggs with expert-assigned DSM scores?
- If not, can we run a data collection campaign? What's the budget for that?
- Do you have physical DSM color fans available for calibration and ground truth?
- What accuracy does the current manual process achieve? (What's the bar we need to clear?)
- Are there regulatory or contractual accuracy requirements tied to these scores?

**Technical constraints:**

- What phone models do your users typically have? (Enterprise-issued or personal devices?)
- Are there specific lighting conditions we should design for? (Open barns, enclosed facilities, labs?)
- Does the app need to store results, generate reports, or integrate with existing feed management or ERP systems?
- Any data privacy requirements? (Where are photos stored? GDPR or similar obligations?)
- Do you need the scoring to happen on-device or is cloud processing acceptable?

**Timeline and team:**

- Is there a launch deadline tied to a trade show, sales cycle, or contract?
- MVP scope vs full product — what's the minimum viable version that's useful?
- Will I be working solo or alongside an internal team?
- Who owns the product decisions? (Who do I go to when there's a tradeoff between accuracy and user experience?)
- Is there budget for ongoing maintenance after launch? Camera software updates, OS changes, and new phone models will require periodic recalibration.
