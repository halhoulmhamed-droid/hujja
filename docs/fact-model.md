# Hujja fact model

**Status:** draft. Derived from [`rules/djim_spdji.yaml`](../rules/djim_spdji.yaml) — this is the
exact set of normalized inputs DJIM requires, and nothing more. Other standards extend it once
their official sources are verified.

Section 4.1 is the specification the Phase 1b EDGAR adapter must satisfy. Section 4.2 is engine
state and is explicitly **not** an adapter responsibility.

## 1. Facts — entity financial inputs

Per entity, per evaluation period, in one consistent reporting currency.

| Fact ID | Description | Unit | Periodicity | Source |
|---|---|---|---|---|
| `non_permissible_activity_revenue` | Revenue attributable to the excluded sectors. **Excludes all interest income** — see the binding constraint in §3.1. | currency | fiscal year | EDGAR + classification judgment; unclear or mixed segments return `DOUBTFUL`, never a guess |
| `interest_income_operating` | Interest income, operating | currency | fiscal year | EDGAR |
| `interest_income_non_operating` | Interest income, non-operating | currency | fiscal year | EDGAR |
| `total_operating_revenue` | Total revenue **excluding** interest income | currency | fiscal year | EDGAR |
| `total_interest_bearing_debt` | Interest-bearing debt, period-end balance | currency | point-in-time | EDGAR — a composition of several tags that filers use inconsistently; a versioned, testable adapter artifact in Phase 1b.1, exposed as a single normalized fact at L1 |
| `market_capitalization` | Trailing 24-month average market capitalization | currency | trailing 24-month average | **Bring-Your-Own-Data** — see §3.2 |

## 2. Prior state — engine inputs

These are not entity facts. They are the output of a previous evaluation run. No adapter can
supply them, and Phase 1b is not expected to.

They are consumed **only** in stateful index-replication mode. In stateless point-in-time mode they
are absent and the transition buffer is not applied.

| State ID | Description | Unit | Periodicity |
|---|---|---|---|
| `prior_period_status` | Status assigned in the previous evaluation period | enum: `COMPLIANT` / `NON_COMPLIANT` | per prior period |
| `consecutive_periods_over_limit` | Count of consecutive evaluation periods in which the leverage ratio **exceeded** the threshold | integer | per prior period |

## 3. Binding constraints on the Phase 1b adapter

### 3.1 `non_permissible_activity_revenue` must exclude all interest income

**This is a correctness constraint, not a style preference.** The DJIM revenue tolerance numerator
sums three facts:

```
non_permissible_activity_revenue + interest_income_operating + interest_income_non_operating
```

"Conventional financial services" is an excluded sector, and a conventional bank's revenue *is*
largely interest income. An adapter that computes `non_permissible_activity_revenue` inclusive of
interest income would therefore count that interest **twice** in the numerator, inflating the ratio
and producing spurious `NON_COMPLIANT` verdicts on exactly the companies the screen matters most
for.

The adapter must supply interest income **only** through `interest_income_operating` and
`interest_income_non_operating`. `non_permissible_activity_revenue` carries non-permissible revenue
net of all interest income.

### 3.2 `market_capitalization` cannot be derived from EDGAR

EDGAR provides shares outstanding (`dei:EntityCommonStockSharesOutstanding`) and an annual public
float (`dei:EntityPublicFloat`), but **no market prices** — and no annual figure can supply a
trailing 24-month average.

The caller supplies this fact. When it is missing, the engine returns `DOUBTFUL` with an explicit
`missing_facts` list. It never substitutes a proxy silently. Any proxy — public float standing in
for market capitalization, for instance — must be an explicit, opt-in, labeled mode whose
divergence from the standard is documented in the output.

## 4. Open items — `TO VERIFY`, not assumed

None of the following is stated in the verified ground truth. Each is recorded as unknown rather
than filled in from memory or inference.

1. **Re-evaluation cadence** for both screens, currently `evaluation_frequency: null`.
   **This is a blocker for Phase 1a.3, not a documentation gap.** `consecutive_periods_before_flip:
   3` is expressed in units of "evaluation period", so without a verified cadence the buffer's
   period count has no defined length and the **stateful index-replication mode is not
   implementable**. The stateless point-in-time mode is unaffected and can ship first.
2. **Sampling method** behind the 24-month average — daily close, monthly, or otherwise.
   `averaging_window` records the window length only.
3. **Symmetric re-entry rule** — whether a non-compliant stock returning below 33% must also wait
   3 consecutive periods before regaining compliant status, or flips back immediately. The verified
   ground truth describes only the compliant → non-compliant direction. This materially affects the
   stateful mode and must not be assumed symmetric.
4. **Currency normalization** for multi-currency filers — an engine-level concern, not addressed by
   the DJIM methodology.

Each item is resolved by reading the official methodology document, not by inference. On
resolution: update the rule file, bump `rule_file.version`, and update the Source verification log
in `README.md`.
