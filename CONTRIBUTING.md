# Contributing

This project exists to be checked. If a threshold, a denominator, an averaging window, or a
source citation is wrong here, that is a bug — and reporting it is the most valuable
contribution you can make.

You do not need to write code to contribute. A message saying *"this rule cites the wrong
version of the methodology"* is worth more than a refactor.

## Who this is for

- **Shariah scholars and Islamic finance practitioners** — reviewing whether a rule faithfully
  reflects the standard it claims to encode.
- **Accountants and analysts** — reviewing whether a ratio maps correctly to reported line items.
- **Developers** — engine, adapters, tests, tooling.

## Reporting a rule error

Open an issue using the **Rule correction** template. Include the official source document, its
version or date, and where it contradicts what this repository states. Screenshots of the
relevant page are welcome; please do not paste long passages of copyrighted standard text — a
citation and a link are enough.

## The one hard rule for pull requests

**Every rule change must cite its source.** A PR touching a rule file must include:

1. the URL of the official methodology or standard document,
2. its version and/or publication date,
3. a version bump of the rule file,
4. an update to the Source verification log in the README.

A PR that changes a threshold without a source will be closed with an invitation to reopen it
with one. This is not bureaucracy — an unsourced threshold is exactly the thing this project
exists to eliminate.

## No verbatim standard text

Screening criteria and numeric thresholds are facts and are not copyrightable. The prose of the
standards is copyrighted. We encode the facts, paraphrase the explanation, and always link to
the official source. Please do not copy paragraphs from AAOIFI, S&P DJI, FTSE Russell, MSCI, or
any other standard-setter into this repository.

## Expert review is recorded, opt-in, and narrow

Rule files carry a `review` block. Being listed there records exactly one thing: that a named
reviewer checked *this version of this rule file* against the official source on that date.

It is **not** an endorsement of the project, **not** a certification, and **not** a fatwa.
Attribution requires your written consent, and you may ask to be removed at any time.

## Disagreements about interpretation

Standards disagree with each other, and scholars disagree about standards. That is expected and
it is the reason this project reports one verdict per standard rather than a merged one.

When a case is genuinely ambiguous, the correct outcome is `DOUBTFUL` plus an open issue — not a
silent choice made by the maintainer. Interpretation debates belong in issues, in the open.

## Language

English is the default for code, rule files, and documentation. French and Arabic documentation
contributions are welcome and valued.

## Conduct

This project touches religious practice and people's money. Disagree with the argument, never
with the person. Bad-faith participation, proselytising for or against any school of thought, and
personal attacks are not welcome here.

## What this project will never accept

- Data under a licence that forbids redistribution (Yahoo Finance, Financial Modeling Prep, or
  any similar feed). Public-domain sources only — SEC EDGAR / XBRL to start.
- Personalized investment recommendations, in code, docs, or issues.
- Any claim that an output of this software is a religious ruling.
