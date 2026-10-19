# WEG equity pipeline

Small project to analyse WEG (WEGE3.SA) from public data. It pulls annual
statements from CVM's open data and prices from Yahoo Finance, computes a few
fundamentals (margins, ROIC, leverage, FCF) and runs a simple DCF. There is a
Streamlit dashboard on top and a script that dumps static charts.

## Running it

```bash
pip install -r requirements.txt
python -m src.etl.ingestion --live
streamlit run app.py
```

`--live` hits CVM and Yahoo, no API key needed. `--mock` uses made-up data from
`tests/fixtures/` so you can run everything offline. Anything produced with
`--mock` is not real WEG data.

For static figures and CSV tables:

```bash
python generate_report.py
```

Output goes to `outputs/`. PNG export needs Chrome for kaleido.

Tests:

```bash
pytest tests/
```

## Layout

- `src/etl/` - ingestion (CVM, yfinance, optional FMP/Brapi)
- `src/analytics/` - KPIs, DCF, market stats
- `src/viz/charts.py` - Plotly charts
- `app.py` - dashboard, `generate_report.py` - static report
- `config/settings.yaml` - WACC, FX and Selic scenarios

## Known issues

- Total debt only picks up one "Empréstimos e Financiamentos" line from CVM, so
  leverage and ROIC are probably off.
- The DCF output needs another look; don't read the target price as a real estimate.

Not investment advice.
