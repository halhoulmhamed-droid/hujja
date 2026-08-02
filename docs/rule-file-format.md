# Hujja rule file format

**Status:** draft. Format version `2.0.0`. Defined to express DJIM and to leave room for the other
standards on the roadmap without a later structural rewrite — but no other standard's thresholds
are encoded until its official source is verified.

A rule file encodes one screening standard as data. Changing a threshold, a comparator, a
denominator, or an averaging window is a change to a rule file — never a change to engine code.

Rule files are written in YAML and validated against
[`src/hujja/schemas/rule-file.schema.json`](../src/hujja/schemas/rule-file.schema.json) (JSON
Schema draft 2020-12). `additionalProperties` is `false` throughout, so an unknown, misspelled, or
policy-bearing field fails loudly instead of entering the contract quietly.

## The one idea behind the format

A verdict is only auditable if a reader can see, in the rule file itself, **what a source states,
what Hujja infers, and what is still unresolved** — separately. Version 2.0.0 exists because
version 1.0.0 could not tell those apart. Most of what follows is a consequence of keeping them
apart.

## Three version fields, never conflated

| Field | Versions what | Example |
|---|---|---|
| `schema_version` | This format | `2.0.0` |
| `rule_file.version` | This file's own content | `1.1.0` |
| methodology edition `label` | The official document's own edition label | `2026-02` |

A change to a rule file's content bumps `rule_file.version`. A change to the format bumps
`schema_version`. **The two numbers are independent and are expected to differ** — format
compatibility is `schema_version`'s job, so a file whose shape migrates does not thereby earn a
content-level major bump. An edition label is assigned by the standard-setter and Hujja never
invents one.

## Top-level structure

| Key | Required | Purpose |
|---|---|---|
| `schema_version` | yes | Version of this format. |
| `rule_file` | yes | `id` and `version` of this file's content. |
| `standard` | yes | `id`, `name`, `provider`, and optional `family` / `series`. Exactly one standard per file. |
| `methodology` | yes | `rule_basis_edition` plus the `editions` it references. |
| `review` | yes | Expert review record. |
| `source_evidence` | yes | Public evidence registry: edition + page locator. |
| `provenance` | yes | Claim-level documentary metadata. |
| `open_decisions` | yes | Hujja implementation choices not yet made. |
| `required_inputs` | yes | Runtime data the engine needs. |
| `operands` | yes | Versioned ratio operands. |
| `cadences` | yes | Index review and evaluation period, kept apart. |
| `business_activity_screen` | no | Excluded activities, mappings, conditional eligibility, tolerance tests. |
| `ratio_screens` | yes | Financial ratio screens. |
| `methodology_change_record` | no | Historical, non-operative records. |
| `purification_methods` | no | Plural container; empty when nothing is encoded. |

### `standard`

One standard per rule file. There is no container for two and no merged-verdict field. Families
that share a brand but differ in denominator — FTSE IdealRatings versus FTSE Shariah, MSCI Islamic
versus MSCI Islamic M — get separate files, and `family` / `series` keep them distinguishable at the
identifier level.

### `methodology` and `rule_basis_edition`

`rule_basis_edition` names the edition this rule file **applies**. It deliberately does not assert
that the edition is the latest one currently published; that is a claim about the world, and this
file cannot verify it.

Each edition carries an `id`, the standard-setter's own `label`, a `role` (`rule_basis` or
`historical_reference`), and a `title`. **Edition identity never depends on a URL.** A URL may be
carried only as inherited tracked content, and only with its limits stated:

```yaml
official_url:
  value: "https://example.invalid/methodology.pdf"
  origin: inherited_from_tracked_rule_file
  edition_specificity: unresolved
  verification_status: unverified
  provenance_ref: pv_official_url_unverified
```

A URL in this shape is not an edition identifier, is not asserted to be edition-specific, and is
not asserted to serve a particular edition permanently. An edition with no inherited URL uses
`official_url: null`.

### `review`

Records exactly one thing: that a named reviewer checked *this version of this rule file* against
the official source on that date. It is not an endorsement, not a certification, and not a fatwa.

`status` is `unreviewed` or `expert_reviewed`, and **the schema closes both states**:

- `unreviewed` → `reviewer`, `scope`, and `date` must all be `null`. A file cannot claim
  `unreviewed` while carrying reviewer metadata.
- `expert_reviewed` → `reviewer` and `scope` must be non-empty strings and `date` must be a
  `YYYY-MM-DD` date. A half-filled review record is rejected.

**A format migration never promotes a file to `expert_reviewed`**, and representing inherited
content more precisely does not make it reviewed.

## Public source evidence

`source_evidence` is the file's public evidence registry. Each entry names an edition, an official
section and page locator, the scope it is offered for, and the stable public anchor:

```yaml
- id: se_2026_appendix_a_ratio
  edition_ref: ed_2026_02
  locator: "Appendix A, PDF 33 / printed 32"
  scope: "Ordinary threshold, comparator, transition band, both transition directions."
  verification_log_ref: "README.md#source-verification-log"
```

`verification_log_ref` is always exactly `README.md#source-verification-log`, and `README.md`
carries an explicit HTML anchor at that point rather than relying on a generated heading slug. The
constraint that makes this useful: **a bare clone of the repository must be able to interpret every
public reference.** Nothing in a rule file may point at material a reader cannot obtain.

## Provenance: three documentary dimensions

Every claim-bearing element reaches a `provenance` entry through a `provenance_ref` (or a named
variant such as `threshold_provenance_ref`). Provenance carries three **independent** dimensions.

### `evidence_basis` — how the conclusion was produced

An array, one or more of `visual_observation`, `native_text_extraction`,
`cross_version_comparison`, `interpretation`, `synthesis`. It is multi-valued because a single
finding can rest on direct reading *and* a comparative judgement at once. **It never determines
documentary resolution:** an interpretive claim can rest on explicit text.

### `documentary_resolution` — what the sources settle

One of `explicit`, `partially_supported`, `unresolved`, `not_found_after_targeted_review`.

This is evaluated **against the declared reviewed evidence set** — the editions and locators the
file names — not against every document that may exist. So:

- absence of a locator does not prove universal source silence;
- it means the declared reviewed evidence set does not establish the claim;
- inherited tracked content lacking a locator is marked `unresolved` against that evidence set;
- it is never described as source-proven or explicit.

`explicit` and `partially_supported` require at least one `source_evidence_refs` entry, enforced by
the schema. `partially_supported` additionally requires `supported_scope` and `unresolved_scope`,
so a partial claim always says which part is which.

**Implementation-choice values are prohibited here.** A pending Hujja decision is not a property of
a source. It lives in `open_decisions` and is reached by `open_decision_ref` — which means a claim
can be *unresolved in the sources* **and** *awaiting a Hujja decision* at the same time, without
either statement overwriting the other.

### `source_consistency` — whether the source material coheres

A **sibling** of `documentary_resolution`, not a value inside it, because the two have different
subjects: resolution is a property of the claim, consistency is a property of the source material
the claim rests on.

```yaml
source_consistency:
  state: not_assessed        # consistent | inconsistent | not_applicable
  scope: null
  note: null
```

A claim may be **explicit and inconsistent at the same time** — a passage can be plainly present
and internally contradictory. Consistency is never inferred from resolution, and it never
influences an operational field.

Two disciplines apply in practice. First, `not_assessed` is the default: a consistency claim is
made only where the evidence explicitly supports one, never from apparent agreement. Second, an
`inconsistent` state requires a non-null `scope` that binds it to the specific passage assessed, so
an observation about one entry can never be read as an indictment of a whole document.

Distinguish carefully between: source **silence** (`unresolved`), **targeted-review
non-discovery** (`not_found_after_targeted_review` — searched and not found, which is not the same
as absent from every source), **incomplete support** (`partially_supported`), and **internal
contradiction** (`source_consistency.state: inconsistent`, at any resolution).

## `open_decisions`

Implementation choices Hujja has not yet made. They never become documentary-resolution values,
source-consistency values, evidence-basis values, or engine defaults.

```yaml
- id: od_sampling_interval
  question: "Observation interval used to construct the trailing 24-month average."
  resolution_paths:
    - "obtain_authoritative_definition"
    - "make_and_disclose_a_separately_reviewed_implementation_decision"
  status: open
  decided_on: null
```

## `required_inputs` and `data_origin`

`required_inputs` declares the runtime data the engine needs. **This is the only place a
`data_origin` object may appear.** A methodology-defined threshold is justified by provenance; it
is not data delivered through a channel, and giving it an origin would confuse the two.

```yaml
data_origin:
  semantic_source: market_observation   # substantive origin
  supplied_via: caller                  # delivery channel
```

The two are separate because they answer different questions and neither is derivable from the
other. One external classification can be proprietary in origin and adapter-supplied in channel;
another can be proprietary in origin and caller-supplied. A single field cannot say that.

`semantic_source` is one of `issuer_financial_data`, `market_observation`, `proprietary_external`,
`engine_prior_state`, `unresolved`. `supplied_via` is one of `caller`, `adapter`, `internal`,
`unresolved`. When the channel is `unresolved`, an `open_decision_ref` is required — an open project
interface is recorded as an open decision, never disguised as a documentary question.
[`docs/fact-model.md`](fact-model.md) remains authoritative for the facts themselves.

Every input carries `absence: {representable: true}`. That records only that a fact snapshot **can
express** the input's absence. **What the engine does about a missing input is not in this
contract** — see "What the format deliberately cannot express".

### External classification inputs

Some screens depend on a proprietary classification that cannot be reproduced from methodology
text. The contract keeps six things apart: the classification **scheme**, an **assignment**, the
**entity** an assignment attaches to, a **code**, the **substantive origin**, and the **delivery
channel**. It also separates **documentary cardinality** (what the sources establish about how many
assignments exist per entity) from the future **adapter contract** shape, so an engineering choice
can never masquerade as a documentary fact.

Observed codes are recorded with `exhaustive: false` and their own per-code provenance. Nothing is
inferred about mutual exclusivity, hierarchy, or taxonomy semantics.

## Versioned operands

Screens reference operands by id rather than embedding fact lists, because a ratio side has a
documentary label, a documentary definition, a computational meaning, an edition scope, and an
evidence status — and these are five different things.

```yaml
- id: op_avg_market_cap_24m
  label: "Trailing 24-month average market capitalization"
  computation:
    input_refs: [in_market_capitalization]
    combination: sum
    averaging_window:
      unit: months
      length: 24
      method: trailing_average
      provenance_ref: pv_window_24m          # the window IS established
      sampling:
        interval: null
        provenance_ref: pv_sampling_unresolved   # the interval is NOT
        open_decision_ref: od_sampling_interval
  documentary_labels: null
  documentary_definitions: null
  documentary_basis_provenance_ref: pv_window_24m
  equivalence_across_editions: null
```

Note the two different `provenance_ref` values inside one operand. **Provenance attaches at the
smallest claim-bearing level**, so an operand can say that its 24-month window is established while
its sampling interval is not. One provenance per object could not express that.

`combination: sum` is the only arithmetic the format expresses. Nothing else has a verified basis.

### Never alias labels across editions

Two editions may use different labels for what looks like the same quantity. Unless equivalence is
established, the format must not treat them as interchangeable. Either use separate operand
identities, or record the relationship explicitly:

```yaml
equivalence_across_editions:
  - edition_a: ed_2023_12
    edition_a_label: "Total Revenue"
    edition_b: ed_2026_02
    edition_b_label: "Total Business Revenue"
    status: not_established
    provenance_ref: pv_denominator_equivalence_unresolved
```

An operand carrying labels from more than one edition requires an `established` equivalence record.
Silence is not equivalence, and aliasing by omission is the failure this structure prevents.

## Cadence separation

An index-review schedule and a transition evaluation period are different things, and version 1.0.0
conflated them by giving a screen a single `evaluation_frequency` field. **That field is gone.**
Nothing in this format equates a review cadence with an evaluation-period length.

```yaml
cadences:
  index_review:
    id: cad_broad_market_review
    applies_to: index_composition       # never transition state
    frequency: quarterly
    months: [3, 6, 9, 12]
    provenance_ref: pv_review_cadence
  evaluation_period:
    id: per_evaluation
    duration: null                      # structured object or null — never a cadence token
    schedule: null
    provenance_ref: pv_eval_period_unresolved
    open_decision_ref: od_evaluation_period_duration
    mapping_to_index_review:
      status: not_established
      provenance_ref: pv_eval_review_mapping_unresolved
      open_decision_ref: od_evaluation_review_mapping
```

`duration` accepts a structured `{unit, length}` object or `null`. A string such as `quarterly` is
**unrepresentable** there by construction. A transition's `period_ref` may target only the
evaluation-period object, never the index review. Setting `mapping_to_index_review.status` to
`established` requires documentary support; the mapping cannot be encoded by inference.

## Bidirectional status transitions

Some standards do not flip a stock's status the moment a ratio crosses a threshold, and the two
directions may be documented differently. The format represents them **separately**, with different
shapes, rather than as one direction-blind buffer:

```yaml
status_transitions:
  state_input_ref: in_prior_period_status
  from_compliant_to_non_compliant:
    tolerance_band:
      width: 0.02
      unit: same_as_threshold
      provenance_ref: pv_transition_band
    within_band:
      status_retained: true
      trigger:
        counter_input_ref: in_consecutive_failing_periods
        required_consecutive_periods: 3
        period_ref: per_evaluation
      provenance_ref: pv_c2n_within_band
    beyond_band:
      immediate_transition:
        availability: present
        provenance_ref: pv_c2n_immediate
  from_non_compliant_to_compliant:
    requires:
      test: ordinary_threshold
      counter_input_ref: in_consecutive_passing_periods
      required_consecutive_periods: 3
      period_ref: per_evaluation
      provenance_ref: pv_n2c_requires
    immediate_transition:
      availability: absent
      absence_basis: superseded
      superseded_by_change_ref: chg_immediate_reentry_replaced
      provenance_ref: pv_n2c_immediate_absent
```

`tolerance_band.width` shares the unit and bounds of `threshold` (both fractions in `0..1`) so the
two can be added directly. Any field mixing fractions with percentage points in one object is a
defect.

### Operational availability is not a documentary label

`availability` is `present`, `absent`, or `not_established` — **operational vocabulary only**. No
boolean is permitted, because a boolean has two states and the contract needs three.

- **`present`** — the route is operationally available. It carries no supersession reference and
  requires provenance resolving to `explicit`.
- **`absent`** — the route is not available, and this requires an **affirmative** documented basis:
  `absence_basis` is `superseded` (a dated change replaced it) or `documented_absent` (the active
  text states there is none). `superseded` additionally **requires** a `superseded_by_change_ref`
  resolving to a non-operative change record; `documented_absent` **forbids** one, because a route
  the active text denies was not replaced by a dated change.
- **`not_established`** — the reviewed evidence does not settle whether an active route exists.

The constraint runs in both directions: if `superseded_by_change_ref` appears at all, then
`availability` must be `absent` **and** `absence_basis` must be `superseded`. Every other
combination — including `absent` + `documented_absent` + a change reference — is rejected by the
schema, so a contradictory transition object cannot be written in the first place.

The separation that matters: **documentary silence never becomes operational absence.** Silence
yields `not_established`; only an affirmative basis yields `absent`. Historical supersession lives
in `methodology_change_record`, documentary resolution lives in provenance, and source consistency
never determines availability.

The buffer's **parameters** are data and live here. **Applying** them — statelessly (point-in-time,
buffer not applied) versus statefully (index replication, buffer applied against prior state) — is
engine behavior and is not encoded in the rule file.

### `methodology_change_record`

Historical entries, each with `normative_use: not_operative`. They exist so a change is visible and
auditable. **A superseded route is never executable as an active route**, and an active rule object
may reach a change record only through a field whose semantics explicitly establish supersession.

## Contextual claims

A screen often carries surrounding documentary context — that an older screen was withdrawn, or
that a published ratio serves a different purpose. Such a statement is worth keeping, but it is not
a rule, and burying several of them in one free-text `description` gives them no individual
documentary status.

`contextual_claims` gives each one its own object and its own provenance:

```yaml
contextual_claims:
  - id: ctx_accounts_receivable_screen_removed
    summary: "An accounts-receivable screen was removed in March 2023."
    provenance_ref: pv_ctx_accounts_receivable_removal_inherited
```

**One claim, one summary, exactly one `provenance_ref`.** Splitting them this way is the whole
point: three statements bundled into one paragraph would share a single documentary status, when in
fact each may be supported, inherited, or unresolved independently.

Contextual claims are **non-executable** and the schema makes that structural rather than advisory.
The object's property set is closed to exactly `id`, `summary`, and `provenance_ref`, so a
threshold, comparator, operand, transition, condition, verdict, or policy field is
*unrepresentable* inside one. A contextual claim never becomes an active rule, and an engine has
nothing to evaluate in it.

When a claim is represented here it is removed from the screen's `description`, so the rule file
states it once. The `description` stays focused on the active, supported computational screen.

## Business activities and conditional eligibility

Excluded activities are structured objects, not flat label strings, because sector screens carry
qualifiers, split categories, and relationships between an entity type and an activity:

```yaml
- id: act_weapons_non_defense
  label: "Weapons and related systems"
  edition_ref: ed_2026_02
  provenance_ref: pv_sector_categories_2026
  qualifiers:
    - kind: deployment_purpose
      summary: "Excluded where deployed for purposes other than defense."
      provenance_ref: pv_weapons_qualifier
  subcategories:
    - id: sub_spyware
      label: "Spyware"
      provenance_ref: pv_weapons_qualifier
```

`nexus_relations` express a relationship between an entity role and an activity, with the
operational effect recorded separately — because observing that a relationship exists in the text
does not establish what it does operationally.

`category_mappings` are first-class edges between editions (`split`, `narrowed`, `reworded`), each
with its **own** provenance and a separately provenanced `consequence`. A textual difference and
its consequence are two claims with two different resolutions: that a category was split may be
established while the eligibility consequence of the rewording is not. **Removal of wording never
establishes eligibility.**

`historical_activities` hold earlier-edition categories with `normative_use: not_operative`, so a
mapping has something to point at without the old category becoming an operative exclusion.

### Incomplete conditions are never executable

A conditional eligibility can override an exclusion under cumulative conditions. When the
conditions are not documented, they must not be encoded as an empty list — an empty `all_of`
evaluates true by vacuous truth, silently turning an unresolved exception into an unconditional
exemption.

```yaml
condition_specification:
  completeness: incomplete
  logic: null
  clauses: null
  provenance_ref: pv_conditional_conditions_unresolved
```

- **incomplete** → `logic` and `clauses` are both `null`. The documentary existence of the
  exception is retained, nothing is executable, and no unconditional exception is implied.
- **complete** → `logic` is `all_of` or `any_of` and `clauses` has at least one entry, each with its
  own provenance path.

An empty array satisfies neither branch, so `clauses: []` is **unrepresentable** — not merely
discouraged. A file with an incomplete condition is still schema-valid: validity means well-formed
and honest, not executable. A consumer detects non-executability by reading
`condition_specification` and decides for itself; the rule file does not choose the consumer's
response.

## Purification

`purification_methods` is an array so distinct methods can never be merged into one object.
Merging them is exactly the error the format exists to prevent — dividend purification and the
AAOIFI holding-based method answer different questions.

An empty array records that no method is encoded. **This is a change from format 1.0.0**, which
stated that purification had no slot at all; the container now exists, but no threshold or formula
is invented to fill it.

## What the format deliberately cannot express

Scope discipline, not oversight:

- **Missing-input policy.** Whether a missing input yields `DOUBTFUL`, a validation error, a manual
  review flag, or something else is an **engine decision and stays outside the rule contract**. The
  format can represent that an input is absent; it must never encode `on_missing`, `if_absent`,
  `fallback`, `default_status`, `default_verdict`, or any verdict token.
- Arithmetic beyond summing inputs.
- Sampling methods for averaging windows, until one is established or separately decided.
- Multi-tier qualitative screens, and any threshold from a standard whose official source has not
  been verified.

## Adding a rule file or changing one

Per the rule-change checklist, a change is incomplete without all four of:

1. The URL of the official methodology document.
2. Its version and/or publication date.
3. A version bump of the rule file.
4. An update to the Source verification log in [`README.md`](../README.md#source-verification-log).

Encode the facts, paraphrase the explanation, link the source. Short edition-specific labels are
recorded as terms of art only where two editions must stay distinguishable. Never reproduce
explanatory prose from any standard-setter.

## Validation

[`tests/test_rule_files.py`](../tests/test_rule_files.py) validates every rule file against the
schema and then checks what JSON Schema cannot express: that every reference resolves to an object
of the right type, that ids are unique, that period references never target the index review, that
consistency is not inferred from resolution, that origin is not derived from documentary metadata,
and that the transition invariants above hold. Run it with the standard library:

```bash
python -B -m unittest discover -s tests -p "test_*.py" -v
```
