# Hujja fact model

**Status:** draft. Derived from
[`src/hujja/rules/djim_spdji.yaml`](../src/hujja/rules/djim_spdji.yaml) — this is the exact set of
normalized inputs DJIM requires, and nothing more. Other standards extend it once their official
sources are verified.

## This document remains authoritative for facts

The rule contract declares, in its `required_inputs` registry, the minimum each input needs for a
rule file to be internally resolvable: an id, a kind, a `data_origin` pair, and a provenance path.
**It does not subsume or replace this document.** Meaning, units, periodicity, adapter obligations,
and the correctness constraints below live here, and where the two are read together this document
governs what a fact *is*.

Section 4 is the specification the Phase 1b EDGAR adapter must satisfy. Section 2 is engine state
and is explicitly **not** an adapter responsibility.

## 1. Entity facts — issuer financial data

Per entity, per evaluation period, in one consistent reporting currency. All of these are
`semantic_source: issuer_financial_data`, `supplied_via: adapter`.

| Input ID | Description | Unit | Periodicity | Source |
|---|---|---|---|---|
| `in_non_permissible_activity_revenue` | Revenue attributable to the excluded activities. **Excludes all interest income** — see the binding constraint in §4.1. | currency | fiscal year | EDGAR + classification judgment; unclear or mixed segments are surfaced for human review, never guessed |
| `in_interest_income_operating` | Interest income, operating | currency | fiscal year | EDGAR |
| `in_interest_income_non_operating` | Interest income, non-operating | currency | fiscal year | EDGAR |
| `in_total_operating_revenue` | Total revenue **excluding** interest income | currency | fiscal year | EDGAR |
| `in_total_interest_bearing_debt` | Interest-bearing debt, period-end balance | currency | point-in-time | EDGAR — a composition of several tags that filers use inconsistently; a versioned, testable adapter artifact in Phase 1b.1, exposed as a single normalized fact at L1 |

## 2. Market observations — not issuer financial data

| Input ID | Description | Unit | Periodicity | Source |
|---|---|---|---|---|
| `in_market_capitalization` | Market capitalization observations, averaged over a trailing 24-month window by the operand that consumes them | currency | see §4.2 | **Bring-Your-Own-Data**, `supplied_via: caller` |

This is a separate category from §1 on purpose. Issuer filings carry share counts but **no
prices**, so market capitalization is not issuer-reported data and cannot be derived from EDGAR at
all. Collapsing the two categories would make that constraint invisible.

## 3. Prior state — engine inputs

These are not entity facts. They are the output of a previous evaluation run. No adapter can supply
them, and Phase 1b is not expected to. All are `semantic_source: engine_prior_state`,
`supplied_via: internal`.

They are consumed **only** in stateful index-replication mode. In stateless point-in-time mode they
are absent and no transition rule is applied.

| Input ID | Description | Unit | Periodicity |
|---|---|---|---|
| `in_prior_period_status` | Compliance status assigned in the previous evaluation period | enum: `COMPLIANT` / `NON_COMPLIANT` | per prior period |
| `in_consecutive_failing_periods` | Count of consecutive evaluation periods in which the ratio **failed** the ordinary test while inside the transition band | integer | per prior period |
| `in_consecutive_passing_periods` | Count of consecutive evaluation periods in which the ratio **satisfied** the ordinary test | integer | per prior period |

### Why there are two counters, not one

The two transition directions are **asymmetric**, and the rule file now encodes that:

- **Compliant → non-compliant.** Status is retained while the ratio stays inside the band; it flips
  after 3 consecutive failing periods; beyond the band an immediate route is available.
- **Non-compliant → compliant.** There is no immediate route. The ordinary test must be satisfied
  for 3 consecutive passing periods. The former immediate re-entry route was replaced effective
  15 September 2023 and is recorded as historical and non-operative.

A single "periods over limit" counter cannot drive both, because the two directions count different
events. This resolves what earlier versions of this document listed as an open question about
whether re-entry was symmetric: it is not, and symmetry must not be assumed.

## 4. Binding constraints on the Phase 1b adapter

### 4.1 `in_non_permissible_activity_revenue` must exclude all interest income

**This is a correctness constraint, not a style preference.** The DJIM revenue tolerance numerator
sums three inputs:

```
in_non_permissible_activity_revenue + in_interest_income_operating + in_interest_income_non_operating
```

"Conventional financial services" is an excluded activity, and a conventional bank's revenue *is*
largely interest income. An adapter that computed `in_non_permissible_activity_revenue` inclusive of
interest income would therefore count that interest **twice** in the numerator, inflating the ratio
and producing spurious non-compliant outcomes on exactly the companies the screen matters most for.

The adapter must supply interest income **only** through `in_interest_income_operating` and
`in_interest_income_non_operating`. `in_non_permissible_activity_revenue` carries non-permissible
revenue net of all interest income.

### 4.2 `in_market_capitalization` cannot be derived from EDGAR

EDGAR provides shares outstanding (`dei:EntityCommonStockSharesOutstanding`) and an annual public
float (`dei:EntityPublicFloat`), but **no market prices** — and no annual figure can supply a
trailing 24-month average.

The caller supplies this input. Any proxy — public float standing in for market capitalization, for
instance — must be an explicit, opt-in, labeled mode whose divergence from the standard is
documented in the output. It is never substituted silently.

### 4.3 External classification is a separate external dependency

`in_classification_assignment` is neither issuer financial data nor a market observation. It is an
externally assigned classification (`semantic_source: proprietary_external`) that **cannot be
reproduced from methodology text**, so no adapter can derive it and no amount of filing data
substitutes for it.

Its delivery channel is `unresolved`: the reviewed sources prescribe no input shape or provider
interface, and Hujja has not chosen one. The rule file records this as an open decision rather than
inventing a channel. Also unresolved and explicitly not inferred: the identity of the classification
scheme, whether the observed codes are the only possible values, how many relevant assignments
exist per entity, and whether assignments are mutually exclusive or hierarchical.

## 5. Missing inputs remain an engine decision

Every input in the rule file carries `absence: {representable: true}`. That records **only** that a
fact snapshot can express the input's absence.

**What the engine does about a missing input is not encoded in the rule contract.** Whether the
outcome is `DOUBTFUL` with an explicit missing-input list, a validation error, a manual-review flag,
or something else is an engine-layer decision, tracked as an open decision in the rule file and
resolved in the engine — not in a rule file. A rule file that encoded a verdict policy would make
the same data mean different things to different consumers, which is the opposite of what the
contract is for.

## 6. Open items — recorded as unresolved, not assumed

Each of the following is carried in the rule file as an explicit open decision rather than filled
in from inference. None blocks the stateless point-in-time mode.

1. **Evaluation-period duration and schedule.** `duration` and `schedule` are `null`. Because
   `required_consecutive_periods` is expressed in evaluation periods, the **stateful
   index-replication mode is not implementable** until this is resolved. The stateless
   point-in-time mode is unaffected and can ship first.
2. **Evaluation-period to index-review mapping.** The quarterly index-composition review is a
   documented index schedule; no reviewed provision maps one evaluation period to one quarterly
   review, so the mapping is `not_established` and must not be assumed.
3. **Sampling interval** behind the 24-month average — daily close, monthly, or otherwise. The
   averaging window records the window length and the trailing-average form only.
4. **External classification** scheme identity, value-space closure, and per-entity cardinality, per
   §4.3.
5. **Currency normalization** for multi-currency filers — an engine-level concern, not addressed by
   the DJIM methodology.

Each is resolved by reading the official methodology document, or by a separately reviewed and
disclosed Hujja decision where the document does not settle it — never by inference. On resolution:
update the rule file, bump `rule_file.version`, and update the Source verification log in
[`README.md`](../README.md#source-verification-log).
