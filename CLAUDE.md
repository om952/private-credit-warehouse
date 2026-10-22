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

## Phases
0. Setup (done)
1. Discovery (done; findings below and in config.py)
2. Extract
3. Transform
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
