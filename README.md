# WEG S.A. (WEGE3.SA) — Fundamental Analysis Pipeline

B3 | Industrials — Electrical Equipment | BRL

Automated equity research pipeline for WEG S.A. Extracts 5 years of pricing and
statement data, computes corporate KPIs, runs a DCF valuation, and exposes a
Streamlit dashboard with Selic × BRL/USD sensitivity.

## Contents

- `src/etl/` — ingestion from yfinance and mock FMP / Brapi endpoints
- `src/analytics/` — ROIC, margins, leverage, FCF yield, DCF model
- `src/viz/` — Plotly exhibits
- `app.py` — Streamlit dashboard
- `tests/` — 9 unit tests (balance sheet, cash flow, DCF, sensitivity)
- `config/settings.yaml` — WACC, FX, and Selic scenario parameters

## Run it

```bash
pip install -r requirements.txt
python -m src.etl.ingestion --ticker WEGE3.SA --period 5y --mock
streamlit run app.py
pytest tests/
```

## What it does

- Downloads daily OHLCV for WEGE3.SA (yfinance)
- Pulls annual income statement, balance sheet, and cash flow (mock FMP/Brapi)
- Tidies JSON into relational Parquet frames
- Computes ROIC, margins, debt ratios, FCF yield, and revenue geography
- Runs a DCF with Gordon-growth terminal value and a target-price sensitivity
  grid over Selic and USD/BRL

## Numbers (base case, mock data)

| Metric | Value |
|---|---|
| Target price | R$ 25.24 / share |
| Enterprise value | R$ 52,206M |
| Equity value | R$ 52,730M |
| WACC | 16.12% |
| ROIC (2024) | 40.1% |
| FCF yield (2024) | 11.6% |

> The fundamental figures are synthetic (mock endpoints) and are not audited
> reported results. This is not investment advice.
