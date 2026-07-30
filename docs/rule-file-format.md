# Hujja rule file format

**Status:** draft. Format version `1.0.0`. Defined to express DJIM and nothing more; other
standards extend this format only after their official sources are verified.

A rule file encodes one screening standard as data. Changing a threshold, a comparator, a
denominator, or an averaging window is a change to a rule file — never a change to engine code.

Rule files are written in YAML and validated against
[`schemas/rule-file.schema.json`](../schemas/rule-file.schema.json) (JSON Schema draft 2020-12) at
load time. `additionalProperties` is `false` throughout, so an unknown or misspelled field fails
loudly instead of being silently ignored.

## Three version fields, never conflated

| Field | Versions what | Example |
|---|---|---|
| `schema_version` | This format | `1.0.0` |
| `rule_file.version` | This file's own content | `1.0.0` |
| `methodology.version` | The official document's own edition label | `2026-02` |

A change to a rule file bumps `rule_file.version`. It bumps `schema_version` only if the format
itself changed, and it never invents a `methodology.version` — that label belongs to the
standard-setter.

## Top-level structure

| Key | Required | Purpose |
|---|---|---|
| `schema_version` | yes | Version of this format. |
| `rule_file` | yes | `id` and `version` of this file's content. |
| `standard` | yes | `id` (canonical machine identifier, e.g. `DJIM_SPDJI`), `name`, `provider`. |
| `methodology` | yes | Provenance: `title`, `version`, `official_url`, `verified_on`. |
| `review` | yes | Expert review record. |
| `business_activity_screen` | no | `excluded_sectors` plus one `tolerance_test`. |
| `ratio_screens` | yes | Array of financial ratio screens. |

### `methodology`

`verified_on` is the date a human or a session read the primary source **in full**. It is not the
date the file was edited. A rule file whose `verified_on` predates a known methodology revision is
stale by definition.

### `review`

Records exactly one thing: that a named reviewer checked *this version of this rule file* against
the official source on that date. It is not an endorsement, not a certification, and not a fatwa.

`status` is `unreviewed` or `expert_reviewed`. When `unreviewed`, the other three fields are
`null`. When `expert_reviewed`, `reviewer`, `scope`, and `date` are all required to be non-empty —
the schema enforces this conditionally. A reviewer is named only with their written consent, and
may withdraw at any time.

### `business_activity_screen`

`excluded_sectors` is a list of `{id, label}` pairs — the activities the standard excludes.
`tolerance_test` is a single **ratioScreen** (below) expressing how much revenue from those
activities the standard tolerates.

## The `ratioScreen` building block

`tolerance_test` and every entry in `ratio_screens` are the same object. One building block covers
both, which keeps the format minimal.

| Field | Required | Notes |
|---|---|---|
| `id`, `label`, `description` | yes | `description` is Hujja's own paraphrase — never text copied from the standard. |
| `numerator` | yes | A **factExpression**. |
| `denominator` | yes | A **factExpression**. |
| `comparator` | yes | One of `<`, `<=`, `>`, `>=`, `==`. |
| `threshold` | yes | A **fraction**, not a percentage: `0.33` means 33%. |
| `evaluation_frequency` | yes | `annual`, `quarterly`, `monthly`, or `null`. |
| `transition_buffer` | no | A **transitionBuffer**. |

### `evaluation_frequency` — required even when unknown

The slot is **required** so that an unverified cadence is explicit rather than invisible. `null`
means the cadence has not been confirmed against the official document (`TO VERIFY`). Omitting the
field is not permitted; the schema rejects it.

This is not cosmetic. `consecutive_periods_before_flip` inside a `transition_buffer` is expressed
in units of "evaluation period" — so a `null` cadence means the buffer's period count has no
defined length, and any stateful mode that depends on it is not implementable until the cadence is
verified.

### `factExpression`

```yaml
numerator:
  facts: [fact_id_a, fact_id_b]
  averaging_window:          # optional
    unit: months
    length: 24
    method: trailing_average
```

`facts` lists fact IDs from the [fact model](fact-model.md). **If more than one is listed, they
are summed.** DJIM never requires anything beyond addition, so no other operation is expressible —
deliberately.

`averaging_window` declares that the side must be pre-averaged over a trailing window before the
comparison. It records the window's **length only**; it does not declare a sampling method, because
no sampling method has been verified against a primary source.

### `transitionBuffer`

Some standards do not flip a stock's status the moment a ratio crosses the threshold. The buffer
declares that behavior as data.

| Field | Notes |
|---|---|
| `tolerance_band` | Width of the band, **as a fraction, in the same unit as `threshold`**. `0.02` means 2 percentage points; with `threshold: 0.33` the buffer ceiling is `0.35`. |
| `consecutive_periods_before_flip` | Periods over the threshold, while inside the band, before the status flips. Period length is `evaluation_frequency` on the same screen. |
| `immediate_breach_beyond_band` | If `true`, a ratio beyond `threshold + tolerance_band` flips the status immediately, without waiting. |

`tolerance_band` shares the unit and the bounds of `threshold` (both are fractions in `0..1`) so
that the two can be added directly. Any field mixing fractions with percentage points in one object
is a defect.

The buffer's **parameters** are data and live here. **Applying** them — statelessly (point-in-time,
buffer not applied) versus statefully (index replication, buffer applied against prior state) — is
engine behavior and is not encoded in the rule file.

## What this format deliberately cannot express

Scope discipline, not oversight. Each of these is added only when a verified official source
requires it:

- Arithmetic beyond summing facts.
- Sampling methods for averaging windows.
- Purification formulas. Purification is a separate concern from compliance screening, and merging
  the two is the exact error the format is built to prevent. A standard's purification ratio is
  recorded as prose in a screen's `description` where relevant, with no slot to fill.
- Multi-tier activity benchmarks, qualitative screens, and total-asset denominators — required by
  other standards, absent from DJIM.

## Adding a rule file or changing one

Per the rule-change checklist, a change is incomplete without all four of:

1. The URL of the official methodology document.
2. Its version and/or publication date.
3. A version bump of the rule file.
4. An update to the Source verification log in `README.md`.

Encode the facts, paraphrase the explanation, link the source. Never reproduce verbatim text from
any standard-setter.
