# Ex-Date Dividend Drift Study

A Streamlit app that studies how a stock or ETF's price behaves around its
dividend **ex-dates**, across four points:

| Point       | Offset | Meaning              |
|-------------|--------|----------------------|
| day_before  | -1     | Close before ex-date |
| ex_date     |  0     | Close on ex-date     |
| day_after   | +1     | Close after ex-date  |
| plus_2      | +2     | Two days after       |

For each point it reports the average **% change** and **$ change** vs. the
prior close, plus the cumulative **drift** measured against the day-before
baseline. It also draws a normalized overlay so every ex-date window lines up
on the same -1/0/+1/+2 axis, with an average-shape line.

Prices are pulled **unadjusted** (`auto_adjust=False`) so high-yield /
option-income ETFs like AMDY aren't distorted by total-return adjustments.

## Run locally

```bash
pip install -r requirements.txt
streamlit run exdate_study_app.py
```

Opens at http://localhost:8501. Enter tickers (comma-separated), a start date,
and an optional end date in the sidebar, then click **Run study**.

## View on an iPhone (deploy free)

1. Create a GitHub repo and push these files (`exdate_study_app.py`,
   `requirements.txt`, this `README.md`).
2. Go to https://share.streamlit.io, sign in with GitHub.
3. Point it at your repo and set the main file to `exdate_study_app.py`.
4. You get a public URL that works in Safari on your phone.

To keep the running machine private instead, run `streamlit run` at home and
use the Network URL (same Wi-Fi) or a tunnel like ngrok / Tailscale.

## Notes

- Data source: Yahoo Finance via `yfinance`. Ex-dates are the dates dividends
  are applied in the price history.
- For option-income ETFs, verify a couple of ex-dates by hand — the price drop
  won't track the distribution cleanly.
- Not investment advice.
