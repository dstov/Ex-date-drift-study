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

POINTS = ["day_before", "ex_date", "day_after", "plus_2", "plus_3"]


@st.cache_data(show_spinner=False)
def fetch_prices(ticker, start, end):
    """Unadjusted OHLC + dividends for one ticker."""
    px = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=False)
    return px


def exdate_study(tickers, start, end):
    """Return (detail_df, summary_df, prices_by_ticker)."""
    detail_rows = []
    capture_rows = []
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
            if idx < 1 or idx + 3 >= len(closes):
                continue
            baseline = closes.iloc[idx - 1]  # day-before-ex close
            div_amt = px["Dividends"].iloc[idx]
            ex_close = closes.iloc[idx]
            price_drop = baseline - ex_close  # positive = price fell
            capture = div_amt - price_drop    # positive = kept value net of drop
            capture_rows.append({
                "ticker": t,
                "ex_date": ex.date(),
                "dividend": round(div_amt, 4),
                "baseline_close": round(baseline, 4),
                "ex_date_close": round(ex_close, 4),
                "price_drop": round(price_drop, 4),
                "capture": round(capture, 4),
                "capture_pct_of_div": (capture / div_amt * 100) if div_amt else float("nan"),
            })
            for lbl, i in zip(POINTS, range(idx - 1, idx + 4)):
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
    capture = pd.DataFrame(capture_rows)
    if detail.empty:
        return detail, pd.DataFrame(), capture, prices

    # Tag each event with an offset (-1,0,+1,+2) for overlay charting
    offset_map = {"day_before": -1, "ex_date": 0, "day_after": 1,
                  "plus_2": 2, "plus_3": 3}
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
    return detail, summary, capture, prices


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
            detail, summary, capture, prices = exdate_study(tickers, start, end or None)
        except Exception as e:
            st.error(f"Error: {e}")
            st.stop()

    if summary.empty:
        st.info("No ex-date events found in the selected range.")
        st.stop()

    # Persist so tabs (e.g. P&L) can recompute without re-fetching
    st.session_state["detail"] = detail
    st.session_state["summary"] = summary
    st.session_state["capture"] = capture
    st.session_state["prices"] = prices

if "summary" not in st.session_state:
    st.info("Set inputs in the sidebar and click **Run study**.")
    st.stop()

detail = st.session_state["detail"]
summary = st.session_state["summary"]
capture = st.session_state["capture"]
prices = st.session_state["prices"]

n_ex = detail["ex_date"].nunique()
st.success(f"{n_ex} ex-date event(s) across {detail['ticker'].nunique()} ticker(s).")

tab_study, tab_pnl = st.tabs(["Ex-Date Study", "Position P&L"])

with tab_study:
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

    # ---- Distribution capture ----
    st.subheader("Distribution capture (dividend vs. ex-date price drop)")
    st.caption(
        "price_drop = day-before close − ex-date close.  "
        "capture = dividend − price_drop.  "
        "Positive capture = price fell less than the payout (you netted value); "
        "negative = the drop exceeded the distribution (return of your own capital)."
    )
    avg_cap = capture["capture"].mean()
    avg_cap_pct = capture["capture_pct_of_div"].mean()
    total_cap = capture["capture"].sum()
    m1, m2, m3 = st.columns(3)
    m1.metric("Avg capture / event ($/sh)", f"{avg_cap:.4f}")
    m2.metric("Avg capture (% of dividend)", f"{avg_cap_pct:.1f}%")
    m3.metric("Total capture ($/sh)", f"{total_cap:.4f}")
    st.dataframe(
        capture.style.format({
            "dividend": "{:.4f}", "baseline_close": "{:.4f}",
            "ex_date_close": "{:.4f}", "price_drop": "{:.4f}",
            "capture": "{:.4f}", "capture_pct_of_div": "{:.1f}",
        }),
        use_container_width=True, hide_index=True,
    )

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
    overlay.index = ["-1 (day before)", "0 (ex-date)", "+1", "+2", "+3"]
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

with tab_pnl:
    st.subheader("Position P&L (total return incl. distributions)")
    st.caption(
        "Enter your lots. Total return = current market value − cost, "
        "plus all distributions paid per share while you held, times shares. "
        "IRA assumption: no tax treatment applied (return-of-capital ignored)."
    )

    pnl_ticker = st.selectbox("Ticker", list(prices.keys()), key="pnl_ticker")
    px = prices[pnl_ticker]
    closes = px["Close"]
    divs = px["Dividends"]
    latest_close = float(closes.iloc[-1])
    latest_date = closes.index[-1].date()
    st.markdown(f"**Latest close:** {latest_close:.4f} on {latest_date}")

    default_lots = pd.DataFrame({
        "buy_date": ["2024-01-01"],
        "shares": [100.0],
        "buy_price": [round(latest_close, 2)],
    })
    st.markdown("Enter one row per lot (buy_date as YYYY-MM-DD):")
    lots = st.data_editor(
        default_lots, num_rows="dynamic", use_container_width=True,
        key="pnl_lots",
    )

    if st.button("Compute P&L", key="compute_pnl"):
        rows = []
        for _, lot in lots.iterrows():
            try:
                bdate = pd.to_datetime(lot["buy_date"]).tz_localize(closes.index.tz) \
                    if closes.index.tz is not None else pd.to_datetime(lot["buy_date"])
                shares = float(lot["shares"])
                bprice = float(lot["buy_price"])
            except (ValueError, TypeError):
                st.warning(f"Skipping invalid row: {lot.to_dict()}")
                continue
            if shares <= 0:
                continue
            # Distributions with ex-date on/after buy date, through latest data
            held_divs = divs[(divs.index >= bdate) & (divs > 0)]
            div_per_share = float(held_divs.sum())
            cost = shares * bprice
            mkt_value = shares * latest_close
            price_pnl = mkt_value - cost
            income = div_per_share * shares
            total_pnl = price_pnl + income
            rows.append({
                "buy_date": pd.to_datetime(lot["buy_date"]).date(),
                "shares": shares,
                "buy_price": round(bprice, 4),
                "cost_basis": round(cost, 2),
                "mkt_value": round(mkt_value, 2),
                "price_pnl": round(price_pnl, 2),
                "distributions_collected": round(income, 2),
                "total_pnl": round(total_pnl, 2),
                "total_return_pct": round(total_pnl / cost * 100, 2) if cost else float("nan"),
            })

        if not rows:
            st.info("No valid lots to compute.")
        else:
            pnl_df = pd.DataFrame(rows)
            tot_cost = pnl_df["cost_basis"].sum()
            tot_price = pnl_df["price_pnl"].sum()
            tot_income = pnl_df["distributions_collected"].sum()
            tot_pnl = pnl_df["total_pnl"].sum()
            tot_ret_pct = tot_pnl / tot_cost * 100 if tot_cost else float("nan")

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Total cost basis", f"${tot_cost:,.2f}")
            k2.metric("Price P&L", f"${tot_price:,.2f}")
            k3.metric("Distributions collected", f"${tot_income:,.2f}")
            k4.metric("Total return", f"${tot_pnl:,.2f}", f"{tot_ret_pct:.2f}%")

            st.dataframe(
                pnl_df.style.format({
                    "shares": "{:.2f}", "buy_price": "{:.4f}",
                    "cost_basis": "${:,.2f}", "mkt_value": "${:,.2f}",
                    "price_pnl": "${:,.2f}", "distributions_collected": "${:,.2f}",
                    "total_pnl": "${:,.2f}", "total_return_pct": "{:.2f}%",
                }),
                use_container_width=True, hide_index=True,
            )
            st.caption(
                "Distributions are summed from each lot's buy date forward, so buying "
                "mid-history only credits payouts you'd actually have received. Price P&L "
                "and distributions are separated so you can see how much of your return is "
                "the underlying moving vs. income collected."
            )
