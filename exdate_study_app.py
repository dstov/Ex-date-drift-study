#!/usr/bin/env python3
"""
Ex-Date Dividend Drift Study — Streamlit browser app

Tracks price behavior around dividend ex-dates:
    day_before (-1), ex_date (0), day_after (+1), plus_2 (+2)

Reports, per point:
    - avg pct change vs prior close
    - avg dollar change vs prior close
    - avg cumulative pct drift vs day-before baseline
    - avg cumulative dollar drift vs day-before baseline

Uses UNADJUSTED close prices (auto_adjust=False) so option-income /
high-yield ETFs like AMDY aren't distorted by total-return adjustments.

Requirements:
    pip install streamlit yfinance pandas

Run:
    streamlit run exdate_study_app.py
Then open the URL it prints (default http://localhost:8501).
"""

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except ImportError:
    yf = None

POINTS = ["day_before", "ex_date", "day_after", "plus_2"]


@st.cache_data(show_spinner=False)
def fetch_prices(ticker, start, end):
    """Unadjusted OHLC + dividends for one ticker."""
    px = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
    return px


def exdate_study(tickers, start, end):
    """Return (detail_df, summary_df, prices_by_ticker)."""
    detail_rows = []
    prices = {}
    for t in tickers:
        px = fetch_prices(t, start, end)
        if px.empty:
            continue
        prices[t] = px
        closes = px["Close"]  # raw, unadjusted
        ex_dates = px["Dividends"][px["Dividends"] > 0].index
        for ex in ex_dates:
            idx = closes.index.get_indexer([ex])[0]
            if idx < 1 or idx + 2 >= len(closes):
                continue
            baseline = closes.iloc[idx - 1]  # day-before-ex close
            div_amt = px["Dividends"].iloc[idx]
            for lbl, i in zip(POINTS, range(idx - 1, idx + 3)):
                prev, cur = closes.iloc[i - 1], closes.iloc[i]
                detail_rows.append({
                    "ticker": t,
                    "ex_date": ex.date(),
                    "dividend": round(div_amt, 4),
                    "point": lbl,
                    "close": round(cur, 4),
                    "pct_change": (cur - prev) / prev * 100,
                    "dollar_change": cur - prev,
                    "cum_pct_drift": (cur - baseline) / baseline * 100,
                    "cum_dollar_drift": cur - baseline,
                })

    detail = pd.DataFrame(detail_rows)
    if detail.empty:
        return detail, pd.DataFrame(), prices

    # Tag each event with an offset (-1,0,+1,+2) for overlay charting
    offset_map = {"day_before": -1, "ex_date": 0, "day_after": 1, "plus_2": 2}
    detail["offset"] = detail["point"].map(offset_map)

    summary = (
        detail.groupby("point")
        .agg(
            avg_pct_change=("pct_change", "mean"),
            avg_dollar_change=("dollar_change", "mean"),
            avg_cum_pct_drift=("cum_pct_drift", "mean"),
            avg_cum_dollar_drift=("cum_dollar_drift", "mean"),
            n=("pct_change", "count"),
        )
        .reindex(POINTS)
        .reset_index()
    )
    return detail, summary, prices


# ----------------------------- UI -----------------------------
st.set_page_config(page_title="Ex-Date Dividend Drift Study", layout="wide")
st.title("Ex-Date Dividend Drift Study")
st.caption(
    "Price behavior around dividend ex-dates using **unadjusted** closes. "
    "Cumulative drift is measured vs. the day-before-ex baseline."
)

if yf is None:
    st.error("yfinance is not installed. Run:  pip install yfinance pandas streamlit")
    st.stop()

with st.sidebar:
    st.header("Inputs")
    tickers_raw = st.text_input("Tickers (comma-separated)", value="AMDY")
    start = st.text_input("Start date (YYYY-MM-DD)", value="2020-01-01")
    end = st.text_input("End date (optional)", value="")
    run = st.button("Run study", type="primary")

if run:
    tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]
    if not tickers:
        st.warning("Enter at least one ticker.")
        st.stop()

    with st.spinner("Fetching…"):
        try:
            detail, summary, prices = exdate_study(tickers, start, end or None)
        except Exception as e:
            st.error(f"Error: {e}")
            st.stop()

    if summary.empty:
        st.info("No ex-date events found in the selected range.")
        st.stop()

    n_ex = detail["ex_date"].nunique()
    st.success(f"{n_ex} ex-date event(s) across {detail['ticker'].nunique()} ticker(s).")

    # ---- Summary ----
    st.subheader("Summary (averaged across all ex-date events)")
    fmt = {
        "avg_pct_change": "{:.4f}",
        "avg_dollar_change": "{:.4f}",
        "avg_cum_pct_drift": "{:.4f}",
        "avg_cum_dollar_drift": "{:.4f}",
    }
    st.dataframe(summary.style.format(fmt), use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Avg cumulative % drift vs baseline**")
        st.bar_chart(summary.set_index("point")["avg_cum_pct_drift"])
    with c2:
        st.markdown("**Avg cumulative $ drift vs baseline**")
        st.bar_chart(summary.set_index("point")["avg_cum_dollar_drift"])

    # ---- Normalized overlay: every event on the same -1..+2 axis ----
    st.subheader("Normalized drift overlay")
    st.caption(
        "Each ex-date window aligned on the same axis (day-before = 0%). "
        "Thin lines = individual events; thick line = average shape."
    )
    metric = st.radio(
        "Overlay metric", ["cum_pct_drift", "cum_dollar_drift"],
        horizontal=True, key="overlay_metric",
    )
    # Pivot: rows = offset (-1..+2), one column per event, plus an Average column
    detail["event_id"] = detail["ticker"] + " " + detail["ex_date"].astype(str)
    overlay = detail.pivot_table(
        index="offset", columns="event_id", values=metric
    ).sort_index()
    overlay["Average"] = overlay.mean(axis=1)
    # Label the offset axis for readability
    overlay.index = ["-1 (day before)", "0 (ex-date)", "+1", "+2"]
    st.line_chart(overlay, use_container_width=True)

    # ---- Price chart with ex-dates ----
    st.subheader("Price with ex-dates marked")
    tick_choice = st.selectbox("Ticker to chart", list(prices.keys()))
    px = prices[tick_choice]
    chart_df = pd.DataFrame({"Close": px["Close"]})
    ex_marks = px["Dividends"][px["Dividends"] > 0].index
    chart_df["ex_date_close"] = px["Close"].where(px.index.isin(ex_marks))
    st.line_chart(chart_df, use_container_width=True)
    st.caption("The 'ex_date_close' series marks the close on each ex-date.")

    # ---- Detail ----
    st.subheader("Per Ex-Date Detail")
    st.dataframe(
        detail.style.format({
            "pct_change": "{:.4f}", "dollar_change": "{:.4f}",
            "cum_pct_drift": "{:.4f}", "cum_dollar_drift": "{:.4f}",
            "close": "{:.4f}", "dividend": "{:.4f}",
        }),
        use_container_width=True, hide_index=True,
    )

    st.download_button(
        "Download detail as CSV",
        detail.to_csv(index=False).encode(),
        file_name="exdate_detail.csv",
        mime="text/csv",
    )
else:
    st.info("Set inputs in the sidebar and click **Run study**.")
