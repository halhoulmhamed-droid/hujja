# Hujja — Open-Source Rules-as-Code Shariah Stock Screening Engine

> **Name.** *Hujja* (حجة — "proof, evidence"): in Islamic legal reasoning, the probative
> argument that establishes a claim. That is precisely what this engine is built to
> produce. The PyPI and GitHub namespaces and the hujja.dev domain were secured on
> 29 July 2026; trademark clearance in MENA jurisdictions is still pending.

**Hujja screens stocks for Shariah compliance using auditable, versioned rules — and returns one
verdict per standard, never a merged black-box answer.**

`License: Apache-2.0` · `PyPI: hujja 0.0.1` · `MCP server: planned` · `Status: pre-alpha`

> **This is not a fatwa and this is not investment advice.** Hujja is an informational and
> educational tool. Its verdicts are mechanical applications of published screening methodologies
> to public financial data. They are not religious rulings, and they are not recommendations to
> buy, sell, or hold any security. Always consult a qualified Shariah scholar and a licensed
> financial professional. See the full [Disclaimer](#disclaimer).

**Status: pre-alpha (design phase).** No code has been published yet. This README is the public
contract that the first release will honor.

---

## Why this exists

Every serious halal stock screener today — Zoya, Musaffa, Islamicly, Finispia, Halal Terminal,
IdealRatings — is closed-source. You receive a verdict; you cannot audit the threshold, the
denominator, the averaging window, or the data snapshot behind it. As of July 2026, we found no
public project that encodes the major Shariah screening standards as auditable open-source logic
(surveyed: the GitHub `islamic-finance` topic, PyPI, and the official MCP registry).

That opacity hides something specific: **the same company can be compliant under one standard and
non-compliant under another.** Thresholds differ, denominators differ (market capitalization vs.
total assets), averaging windows differ, sector lists differ. A single merged verdict silently
picks a winner for you.

So Hujja's first published dataset will be a **divergence matrix**: for a broad US index, every
company's verdict under every encoded standard, side by side, as open data. We have not computed
it yet and we will not quote a headline number before we have — the matrix will report it.

The engine is built on five commitments:

1. **Rules as code, versioned.** Every rule lives in a declarative file carrying its threshold,
   numerator, denominator, averaging window, the version and date of the methodology it was taken
   from, and the URL of the official source document.
2. **One verdict per standard.** Hujja reports each standard's verdict side by side and never
   merges them. The divergence *is* the information.
3. **Reproducible.** `verdict = f(rules manifest, facts snapshot)`. Same rule versions + same
   financial facts = same verdict, every time, with a structured evidence trail citing the exact
   rule applied.
4. **Public data only.** The engine and any published verdicts are computed exclusively from
   public sources (SEC EDGAR / XBRL). No licensed market data is redistributed in this repository.
5. **Human-in-the-loop.** Ambiguous cases (mixed activities, unclear revenue segments) return
   `DOUBTFUL` and are flagged for expert review — never silently auto-resolved.

## Supported standards

### v0 scope — verified against current official sources

| Standard | Financial screens (paraphrased summary) | Denominator / window | Source (official) |
|---|---|---|---|
| **AAOIFI Shariʿah Standard No. 21** (as amended by SS 59) | Interest-bearing debt ≤ 30%; interest-bearing deposits/investments ≤ 30%; non-compliant income < 5% of total income; core business activity must be permissible. The former liquidity screen was removed by Standard No. 59. | Market capitalization | [AAOIFI e-standards](https://aaoifi.com/e-standards/?lang=en) |
| **Dow Jones Islamic Market — DJIM (S&P DJI)** | Sector screens (alcohol; tobacco & e-cigarettes; recreational cannabis; pork-related; conventional financial services; non-defense weapons incl. spyware; gambling; adult entertainment) with a 5% tolerance where non-permissible revenue *includes all interest income*. **Single accounting screen:** total interest-bearing debt / trailing 24-month average market capitalization < 33%. | 24-month average market capitalization | [S&P DJI — DJIM Methodology, Feb 2026](https://www.spglobal.com/spdji/en/documents/methodologies/methodology-dj-islamic-market-indices.pdf) |

**Two facts many screeners still get wrong** (verified in the February 2026 S&P DJI document):

- DJIM's old "three ratios < 33%" description is **obsolete**: a single *Leverage Compliance*
  filter remains, and that much is established by an edition and page locator. The two removal
  dates usually quoted alongside it — an accounts-receivable screen in March 2023 and a
  cash + interest-bearing-securities screen in September 2023 — are **carried forward from earlier
  work in this repository and were not re-established** by the evidence behind the current rule
  file. They are recorded there as inherited, unresolved context rather than as verified facts.
- DJIM applies a **transition buffer, and it is not symmetric.** Going *out* of compliance, a stock
  crossing the 33% line keeps its previous status while the ratio stays within 2 percentage points
  of the limit, flips after 3 consecutive evaluation periods, and flips immediately beyond the
  buffer. Coming *back*, there is no immediate route: the ordinary test must be satisfied for 3
  consecutive evaluation periods. The former immediate re-entry route was replaced effective
  15 September 2023 and Hujja records it as a historical, non-operative entry. Faithful index
  replication therefore requires *state*, and the two directions are encoded separately.

### Roadmap standards — encoded only after verifying the current official version

Several index providers publish **two families under one brand name, with different denominators.**
Conflating them is the most common error in secondary sources, so Hujja encodes each family as a
separate standard with its own rule file:

| Family | Denominator | Note |
|---|---|---|
| **FTSE IdealRatings Islamic Index Series** | 12-month average market capitalization (debt ≤ 30%) | [Ground rules](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/ftse-idealratings-islamic-index-series-ground-rules.pdf) |
| **FTSE Shariah (Yasaar-screened)** | Total assets (33.33%) | Distinct family — never merge with the above |
| **MSCI Islamic Index Series** | Total assets | MSCI: "Uses total assets as denominator" |
| **MSCI Islamic Index M Series** | Average market capitalization | MSCI: "Uses average market capitalization as denominator" |

Both MSCI families share the business-activity screen but differ on the financial ratios; MSCI
describes them as offered together "to accommodate client preferences"
([MSCI Islamic Indexes](https://www.msci.com/indexes/group/islamic-indexes) ·
[latest methodology](https://www.msci.com/index/methodology/latest/Islamic)). Exact ratio values
and thresholds are to be read from the current methodology document before encoding.

**SC Malaysia (Shariah Advisory Council)** — two-tier activity benchmarks (5% / 20%); cash/total
assets and debt/total assets each < 33%; plus a qualitative screen. The SAC's official
semi-annual list (effective the last Friday of May and November; the November 2025 list took
effect 28 Nov 2025, with 859 of 1,073 securities ≈ 80% classified compliant) doubles as Hujja's
**external validation benchmark** — no competitor publishes such a check.
[Official page](https://www.sc.com.my/development/icm/shariah-compliant-securities).

Each rule file records the exact methodology version and date it encodes. When a standard changes,
the rule file is versioned — old verdicts remain reproducible against old rules.

## How a verdict is produced

```
normalized financial facts (SEC EDGAR / XBRL)
        │
        ▼
┌─────────────────────────────┐
│  rules engine               │  ← declarative rule files, one set per standard,
│  (pure Python, no I/O)      │    each versioned + linked to its official source
└─────────────────────────────┘
        │
        ▼
one verdict PER STANDARD: COMPLIANT | NON_COMPLIANT | DOUBTFUL
+ structured evidence trail (JSON)
```

Target output schema (illustrative, subject to change before v0.1):

```json
{
  "entity": { "name": "Example Corp", "ticker": "XMPL", "cik": "0000000000" },
  "facts_snapshot": {
    "source": "SEC EDGAR (XBRL), 10-K FY2025",
    "retrieved": "2026-07-28",
    "hash": "sha256:…"
  },
  "rules_manifest": { "version": "0.1.0", "hash": "sha256:…" },
  "verdicts": [
    {
      "standard": "AAOIFI_SS21",
      "status": "COMPLIANT",
      "review": {
        "status": "expert_reviewed",
        "reviewed_by": "…",
        "scope": "rule file v0.1.0 checked against official source",
        "date": "2026-07-28"
      },
      "checks": [
        {
          "rule_id": "aaoifi_ss21.interest_bearing_debt_to_market_cap",
          "threshold": 0.30,
          "observed": 0.184,
          "pass": true,
          "source": {
            "document": "AAOIFI Shari'ah Standard No. 21 (as amended by SS 59)",
            "url": "https://aaoifi.com/e-standards/?lang=en"
          }
        }
      ]
    },
    {
      "standard": "DJIM_SPDJI",
      "status": "DOUBTFUL",
      "review": { "status": "unreviewed" },
      "review_required": true,
      "notes": ["Revenue segment 'entertainment' requires human classification."]
    }
  ],
  "disclaimer": "Not a fatwa. Not investment advice."
}
```

`DOUBTFUL` is a first-class status, not a failure mode. Mixed or ambiguous cases are surfaced for
qualified human review, and community-validated classifications flow back in through pull requests.

Every rule file carries a `review` block, and every verdict propagates it. A rule that no
qualified reviewer has checked is labeled `unreviewed` in the output — visibly, not silently.

## Purification

Hujja computes **two distinct purification methods and never merges them into one formula**:

1. **Dividend purification** (the common index/screener practice; DJIM publishes this ratio and
   explicitly labels it a purification aid, not a compliance ratio):
   `dividends × (non-permissible income / total income)`.
2. **AAOIFI SS 21 holding-based method**: the impermissible income attributable to each share
   held — the obligation follows the holding, not only the cash dividend received.

Both outputs are labeled with their method and source.

## Data policy (hard rules)

- **In this repository:** SEC EDGAR / XBRL only (public-domain filings of US issuers), plus
  verdicts and facts derived from them.
- **Never in this repository:** Yahoo Finance data (its terms are personal-use only), Financial
  Modeling Prep data (redistribution/display requires a specific licensing agreement), or any
  other licensed feed. Commercial products built on the engine must license their own data; the
  open-source engine stays clean.

## Target API (subject to change)

```bash
pip install hujja
```

```python
from hujja import Engine

engine = Engine(standards=["AAOIFI_SS21", "DJIM_SPDJI"])
report = engine.screen(facts)      # facts: normalized fundamentals from EDGAR/XBRL

for verdict in report.verdicts:    # one verdict per standard — never merged
    print(verdict.standard, verdict.status)

report.to_json()                   # full evidence trail, hashes included
```

**Agent-ready adapters (planned).** All of these are thin wrappers over the same engine and the
same rule files — no separate logic, no divergent behavior: CLI, FastAPI service, MCP server (to
be published to the official MCP registry), Claude Skill (`SKILL.md`), OpenAI function-calling
schema, LangChain tool. Plus a public verdicts dataset (Hugging Face + Zenodo DOI).

## What Hujja is not

- **Not a fatwa** and not a substitute for a qualified Shariah scholar.
- **Not investment, legal, or tax advice**, and never a personalized recommendation.
- **Not a single halal/haram oracle.** Standards disagree; Hujja shows you where and why.
- **Not a market-data vendor.** It redistributes no licensed data.

## Roadmap

- **Phase 1a — engine.** Pure-Python library; AAOIFI SS 21 + DJIM (Feb 2026 version) rule files;
  verdicts for ~50–100 large US companies from EDGAR; tests; evidence JSON.
- **Phase 1b — coverage & docs.** Documentation site; FTSE (both families, kept separate), MSCI
  (both series, kept separate), and SC Malaysia rule files after source verification; benchmark of
  Hujja's SC Malaysia rules against the official SAC list.
- **Phase 1c — ecosystem.** Divergence matrix as an open dataset (Hugging Face + Zenodo DOI);
  purification module (two methods); FastAPI service; MCP server + official MCP registry entry;
  agent adapters.

## Contributing

Contributions are welcome — especially from Shariah scholars, Islamic finance practitioners, and
accountants.

- **Every rule change must cite its source.** A PR touching a rule file must include the official
  methodology URL, its version/date, and a version bump of the rule file.
- **No verbatim standard text.** We encode rules as facts and paraphrase; the underlying standard
  documents are copyrighted, and readers are always linked to the official source.
- **Expert review is recorded, opt-in, and narrow.** A `review` block names a reviewer only with
  their written consent, and records exactly one thing: that this reviewer checked *this version
  of this rule file* against the official source on that date. It is not an endorsement of the
  project, not a certification, and not a fatwa. Reviewers may withdraw at any time.
- Ambiguity taxonomy (`DOUBTFUL` cases) is debated openly in issues.
- English is the default language; French and Arabic documentation contributions are welcome.

## FAQ

**Why one verdict per standard instead of a single answer?**
Because the standards genuinely differ — in thresholds, denominators (market capitalization vs.
total assets), averaging windows, and sector rules. Any single merged answer hides a judgment call
someone else made for you. Hujja's job is to make that judgment visible.

**Is stock X halal?**
Hujja will tell you how stock X evaluates *under each encoded standard*, with the numbers and the
rule citations. Whether that makes it acceptable for you is a question for you and a qualified
scholar.

**Why only large US companies at first?**
SEC EDGAR/XBRL is the only large public-domain source of audited fundamentals. Starting there
keeps the open-source repository free of licensed data. Coverage expands as compliant public
sources are added.

**Can I use this in my product?**
Yes — Apache-2.0. Keep the attributions and the disclaimers; the verdicts remain informational
only.

## License

Apache License 2.0 — engine and rule files. Commercial applications built on top of the engine are
separate products and do not gate anything in this repository (open-core model).

## Disclaimer

Hujja is provided for informational and educational purposes only. It does not issue fatwas, does
not provide investment, legal, accounting, or tax advice, and does not make personalized
recommendations of any kind. Screening outcomes differ across standards by design and depend on
the accuracy and timeliness of public filings, which may contain errors or omissions. No
maintainer or contributor accepts liability for decisions made on the basis of this software or
its outputs. Before acting, consult a qualified Shariah scholar and a licensed financial
professional in your jurisdiction.

<a id="source-verification-log"></a>

## Source verification log

Hujja holds itself to the standard it asks of others: every claim above is dated, and this table
is re-checked at each release. A source not re-verified for a release is marked as such rather
than silently carried over.

Every `source_evidence` entry in a rule file points back to this section. Each one names an
official methodology edition and a section/page locator, so a reader who obtains the edition can
check the claim without any private material.

| Source | Version encoded | Last verified | Status |
|---|---|---|---|
| S&P DJI — DJIM Methodology | February 2026 | 2026-07-28 | Encoded. Per-claim locators ship in the rule file; the categories below say what each locator does and does not establish |
| AAOIFI — Shariʿah Standard No. 21 (w/ SS 59) | Current e-standards edition | 2026-07-28 | Portal & free access confirmed; thresholds to re-check in the official text before encoding |
| SC Malaysia — SAC list | November 2025 (effective 28 Nov 2025) | 2026-07-28 | Official page confirmed; May 2026 list to be pulled |
| FTSE IdealRatings Islamic Index Series | Ground rules (current) | 2026-07-28 | Link confirmed; ratios not yet read in full |
| FTSE Shariah (Yasaar) | — | Not verified | Blocking before encoding |
| MSCI Islamic Index Series / M Series | Two-series split confirmed | 2026-07-28 | Denominators confirmed on MSCI's index page; thresholds not yet read in the methodology PDF |

### What the DJIM rule file claims, and at what strength

Resolution below is stated **against the declared reviewed evidence set** for the rule file — the
editions and locators it names. Where a claim carries no locator, that means this evidence set does
not establish it. It is not a claim that every possible source is silent.

**Supported by an edition and page locator.** The single active accounting-based ratio screen; its
33% threshold and strictly-below comparator; the 2-percentage-point transition band; both
transition directions and the three-consecutive-period counts; the trailing 24-month average
denominator and its trailing-average form; the quarterly index-composition review schedule; the
gambling, adult entertainment, pork-related and weapons categories, the weapons deployment-purpose
qualifier, the pork-selling nexus, and the split of the earlier entertainment category into two;
the **5% revenue-tolerance level** and the February 2026 revenue-tolerance denominator label; the
dependence on an external classification and the two observed classification codes.

Each of these claims carries provenance scoped to that claim alone. The 5% threshold's provenance,
for instance, establishes the tolerance **level** and nothing else — not the comparator applied to
it and not the measurement basis of its denominator, which are separate claims listed below.

**Partially supported.** None at present. The category is retained because the contract expresses
it and a future claim may need it.

**Inherited from the tracked rule file, without a locator in this evidence set.** The leverage
numerator's label and definition; the alcohol, tobacco and e-cigarettes, recreational cannabis, and
conventional financial services categories; the revenue-tolerance comparator; and the numerator and
denominator compositions of the revenue-tolerance test.

Also inherited, and now recorded as three individually provenanced contextual claims on the
leverage screen rather than as prose:

- an **accounts-receivable** screen was removed in **March 2023**;
- a cash-plus-interest-bearing-securities screen was removed in **September 2023**;
- the separately published dividend ratio is a **purification aid** rather than a compliance ratio.

All of these values are preserved and computable, and each is marked unresolved rather than
presented as source-established. Also inherited: the methodology URL and the 2026-07-28
verification date shown above. The URL is carried as inherited tracked content only — it is **not**
treated as an identifier of the February 2026 edition, its edition specificity is unresolved, and
neither it nor the inherited date is presented as newly verified for that edition.

**Unresolved and recorded as open decisions.** The duration and scheduling of an evaluation period;
whether one evaluation period maps to one quarterly index review; the observation interval used to
build the trailing 24-month average; the identity of the external classification scheme and the
number of relevant assignments per entity; the conditions of the external-classification
eligibility exception and which excluded activity it qualifies; the delivery channel and adapter
contract for classification assignments; and engine behaviour when a required input is absent. None
of these is guessed, and none is resolved by inference from another.

**Historical, non-operative.** The former immediate re-entry route replaced effective
15 September 2023, and the earlier entertainment category. Both are recorded so the change is
visible, and neither is executable as an active rule.

**Review status.** The DJIM rule file remains `unreviewed`. Representing inherited content more
precisely does not make it expert-reviewed, and no rule file is promoted by a format migration.

## References (official sources)

- AAOIFI — Shariʿah standards, free official e-standards portal:
  <https://aaoifi.com/e-standards/?lang=en>
- S&P Dow Jones Indices — *Dow Jones Islamic Market Indices Methodology*, February 2026:
  <https://www.spglobal.com/spdji/en/documents/methodologies/methodology-dj-islamic-market-indices.pdf>
- Securities Commission Malaysia — *List of Shariah-Compliant Securities* (SAC, semi-annual):
  <https://www.sc.com.my/development/icm/shariah-compliant-securities>
- FTSE Russell — *FTSE IdealRatings Islamic Index Series Ground Rules*:
  <https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/ftse-idealratings-islamic-index-series-ground-rules.pdf>
- MSCI — Islamic Indexes overview (two series, two denominators):
  <https://www.msci.com/indexes/group/islamic-indexes>
- MSCI — *MSCI Islamic Index Series Methodology* (latest):
  <https://www.msci.com/index/methodology/latest/Islamic>

*A note on copyright: numeric thresholds and screening criteria are facts and are not
copyrightable (see* Feist Publications v. Rural Telephone*, 499 U.S. 340 (1991)). Hujja encodes
those facts, paraphrases everything else, and always links to the official documents — it never
reproduces standard texts verbatim.*
