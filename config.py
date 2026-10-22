BDC_TICKERS = ["ARCC", "OBDC", "GBDC", "FSK", "MAIN"]
N_QUARTERS = 8

# Confirmed against ARCC 10-Q 2026-06-30 (0001628280-26-050307), arcc-20260630_htm.xml.
# Same element names and loan axis also present in OBDC/GBDC/FSK/MAIN 2026-06-30 10-Qs.
FACT_ELEMENTS = {
    "us-gaap:InvestmentOwnedAtFairValue": "fair_value",
    "us-gaap:InvestmentOwnedAtCost": "cost",
    "us-gaap:InvestmentOwnedBalancePrincipalAmount": "principal",
    "us-gaap:InvestmentBasisSpreadVariableRate": "spread",
    "us-gaap:InvestmentInterestRate": "interest_rate",
    "us-gaap:InvestmentInterestRatePaidInKind": "pik_rate",
}
# One investment = one context whose only dimension is this typed axis.
# Member text is "<issuer> | <instrument>[ n]" (ARCC; format differs per BDC).
# Keep only members with both fair value and cost: FV-only members are issuer
# subtotals from the affiliate rollforward tables and double count.
INVESTMENT_AXIS = "us-gaap:InvestmentIdentifierAxis"

# Maturity date is NOT tagged in XBRL by any of the 5 BDCs. For ARCC it, industry,
# and reference rate come from the HTML Schedule of Investments: each <tr> carries
# ix:nonFraction contextRefs; industry = preceding bold single-cell row;
# maturity = second MM/YYYY cell (first is acquisition date).
INDUSTRY_AXIS = "us-gaap:EquitySecuritiesByIndustryAxis"  # FV subtotals per industry, no loan link

# Reconciliation total: InvestmentOwnedAtFairValue with no dimensions at the period-end instant.
TOTAL_FV_ELEMENT = "us-gaap:InvestmentOwnedAtFairValue"
