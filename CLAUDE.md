# Private Credit Loan Analytics Warehouse

## Goal
Build a pipeline that extracts loan-level Schedule of Investments data from SEC BDC
filings (EDGAR XBRL), loads it into a Snowflake star schema with reconciliation checks,
runs a yield-method valuation with spread sensitivity, and feeds a Tableau dashboard.
Work proceeds phase by phase.

## Hard rules
- Minimal, working code only. No extra files, classes, abstractions, tests, logging
  frameworks, CLI arg parsing, or config systems.
- Plain Python functions and scripts. Every script runs standalone and is rerunnable.
- Allowed libraries only: requests, lxml, pandas, numpy, python-dotenv,
  snowflake-connector-python[pandas].
- Data modeling happens in SQL inside Snowflake, not Python.
- Secrets come from environment variables: SEC_USER_AGENT, SNOWFLAKE_ACCOUNT,
  SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE,
  SNOWFLAKE_SCHEMA. Never hardcode them.
- SEC requests: always send the User-Agent header from SEC_USER_AGENT, max 10 req/sec.
- Never commit data/raw/ (it is in .gitignore).
- Don't guess XBRL element names. Verify them from real files.

## Target structure (do not add anything beyond this)
CLAUDE.md, config.py, extract.py, transform.py, load.py, valuation.py, run.py,
sql/schema.sql, sql/recon.sql, sql/views.sql, data/raw/, data/clean/,
requirements.txt, .gitignore, README.md

## Scope
- Build the full pipeline end to end on ARCC first, then add GBDC, then MAIN.
  FSK and OBDC are optional. One BDC at a time.
- Spread is the key metric; coupon (interest rate) is optional.
- Snowflake env vars are intentionally not set in the cloud environment. Phases 2-3
  don't need them; the user loads data/clean/*.csv into Snowflake from a laptop.
- data/raw/ is gitignored, but data/clean/*.csv IS committed (needed for the Phase 4 load).

## Phases
0. Setup (done)
1. Discovery (done; findings below and in config.py)
2. Extract (done for ARCC: extract.py -> data/raw/ARCC/{period_end}.xml/.htm)
3. Transform (done for ARCC: transform.py -> data/clean/loans.csv, reported_totals.csv)
4. Snowflake load
5. Reconciliation
6. Valuation
7. Tableau views
8. README

## Discovery findings (ARCC 10-Q 2026-06-30)
- Loan facts: InvestmentOwnedAtFairValue, InvestmentOwnedAtCost,
  InvestmentOwnedBalancePrincipalAmount, InvestmentBasisSpreadVariableRate,
  InvestmentInterestRate, InvestmentInterestRatePaidInKind (all us-gaap).
  Rates are decimals (0.0865); amounts are full USD.
- Investment = context with only us-gaap:InvestmentIdentifierAxis (typed member,
  free text like "ACP Avenu Midco LLC | First lien senior secured loan 2").
- Drop members that have FV but no cost (issuer subtotals). With that rule, the
  loan-level FV sum equals the no-dimension total exactly for both periods.
- No maturity date element in XBRL (all 5 BDCs). Maturity, industry and reference
  rate come from the HTML SOI rows, joined on contextRef.
- Lien type only exists in member text / HTML instrument column.
- Each filing has two balance dates (current quarter-end and prior year-end).

## Transform findings (ARCC, 8 periods 2024-09-30 .. 2026-06-30)
- Investment = InvestmentIdentifierAxis (or, in 2 filings, InvestmentIssuerNameAxis) context
  with FV and cost whose FV fact sits on a dated HTML SOI row. FV+cost alone is not enough:
  the 10-Ks and 2025 10-Qs tag some issuer subtotals with cost. Reconciles exactly in 7 of 8
  periods; 2025-03-31 is short $2.3M (one row whose cost is tagged on another context).
- Borrower and instrument come from the HTML row, not member text: older members use ",",
  no separator, or are mislabeled (wrong instrument or even wrong issuer vs the row's facts).
- Loans without spread are fixed-rate, PIK-only fixed, non-accrual (no coupon shown) or
  $0 unfunded commitments.
- Industry names change across periods (GICS reclassification, e.g. "Health Care Services"
  -> "Health Care Equipment and Services"); map them in SQL if needed.
