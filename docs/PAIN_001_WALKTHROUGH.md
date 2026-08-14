# PAIN-001 walkthrough — Context-aware receipt-to-job matcher

## Story concept

The receipt is correct. The project assignment is wrong.

That creates a stronger visual story than “AI reads a receipt.” Reading OCR is not the insight. The intelligent part is combining messy receipt content with business context and knowing when confidence is too low to auto-route.

## 58-second scene plan

| Scene | Time | Type | Purpose |
|---|---:|---|---|
| S01 | 0–4 | talking head | Hook / credibility |
| S02 | 4–9 | HyperFrames graphic | One receipt branches to three possible jobs |
| S03 | 9–17 | Playwright | Receipt fields extracted |
| S04 | 17–22 | talking head | Explain what is actually hard |
| S05 | 22–30 | HyperFrames diagram | Worker + schedule + supplier + items + history |
| S06 | 30–38 | Playwright | 94% confident Riverside match |
| S07 | 38–43 | talking head | “Good AI should know when it does not know” |
| S08 | 43–49 | Playwright | Ambiguous receipt → REVIEW 61% |
| S09 | 49–54 | HyperFrames graphic | DIY stack |
| S10 | 54–58 | talking head CTA | Custom integration signal |

## Prototype

`04_prototype/index.html` is a synthetic local app with stable `data-testid` selectors. It exposes three deterministic states:

1. receipt extraction;
2. confident job match;
3. ambiguous review state.

## Screen recording

`05_asset_jobs/` contains three independent Playwright manifests. They can be rerun separately, so a failed or visually weak S08 does not force S03/S06 to be recorded again.

## Talking head

Record four short clips, not one 58-second monologue. This makes presenter production batchable across episodes and lets the Director control pacing.

## Composition

Before your presenter clips exist, render the preview with placeholders. Once the edit feels correct, import S01/S04/S07/S10 and rerender only the final composition.
