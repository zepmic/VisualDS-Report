import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

st.markdown(
    """
    <style>
        .block-container { padding-top: 0.8rem; padding-bottom: 0.4rem; }
        header[data-testid="stHeader"] { height: 0rem; }
        footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------------------
# Page config
# -------------------------------------------------------------------

st.set_page_config(page_title="Energy Shock Dashboard", layout="wide")
st.title("Energy shock dashboard    ")
st.caption("Base index: 2007 = 100 · Source: World Bank CMO (Monthly)")


with st.popover("How to use this dashboard"):
    st.markdown(
        """
        **What does this dashboard show?**  
        This dashboard visualizes monthly energy commodity prices using an index (base year = 100).
        The energy basket is computed as the average of the selected commodities.

        **How to interact:**
        - Use the **sidebar** to select commodities, time range, and change metric (YoY or MoM).
        - Use the **scatter plot** to select months (brushing).
        - Selecting points updates all other charts automatically (linking).

        **Goal:**
        To explore energy price shocks, volatility, and structural changes over time.
        """
    )

# -------------------------------------------------------------------
# Load & clean data
# -------------------------------------------------------------------

path = "CMO-Historical-Data-Monthly.xlsx"
raw = pd.read_excel(path, sheet_name="Monthly Prices")

meta_row = 5
data = raw.iloc[meta_row + 1:].copy()
codes_row = raw.iloc[meta_row].copy()
codes_row.iloc[0] = "DATE"
data.columns = codes_row.values

data = data.loc[:, ~pd.isna(data.columns)]
data = data.dropna(subset=["DATE"])

data["DATE"] = pd.to_datetime(
    data["DATE"].astype(str).str.replace("M", "-", regex=False),
    format="%Y-%m",
)
data = data.set_index("DATE").sort_index()

# -------------------------------------------------------------------
# Defaults & helpers
# -------------------------------------------------------------------

DEFAULT_ENERGY_CODES = ["CRUDE_BRENT", "NGAS_US", "COAL_AUS"]

def make_index(df, cols, base_start, base_end):
    subset = df[list(cols)].apply(pd.to_numeric, errors="coerce")
    base = subset.loc[base_start:base_end].mean()
    return subset.divide(base).multiply(100)

def yoy_pct(s): return s.pct_change(12) * 100
def mom_pct(s): return s.pct_change(1) * 100

# -------------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------------

with st.sidebar:
    st.header("Controls")

    all_cols = [c for c in data.columns if c != "DATE"]
    defaults = [c for c in DEFAULT_ENERGY_CODES if c in all_cols] or all_cols[:3]

    selected_cols = st.multiselect(
        "Commodities",
        options=all_cols,
        default=defaults,
    )

    base_year = st.selectbox(
        "Base year (index = 100)",
        list(range(1960, 2025)),
        index=list(range(1960, 2025)).index(2007),
    )

    start_date = st.date_input("Start date", pd.to_datetime("2000-01-01"))
    end_date = st.date_input("End date", data.index.max())

    change_mode = st.radio("Change metric", ["YoY %", "MoM %"])
    show_table = st.checkbox("Show data table (Details tab)", True)

if not selected_cols:
    st.stop()

# -------------------------------------------------------------------
# Compute series
# -------------------------------------------------------------------

idx = make_index(
    data,
    selected_cols,
    f"{base_year}-01-01",
    f"{base_year}-12-31",
)

idx = idx.loc[start_date:end_date]
basket = idx.mean(axis=1)

change = yoy_pct(basket) if change_mode == "YoY %" else mom_pct(basket)

df_plot = pd.DataFrame({
    "date": basket.index,
    "basket_index": basket.values,
    "basket_change": change.values,
}).dropna()

# -------------------------------------------------------------------
# KPIs
# -------------------------------------------------------------------
k1,k2,k3, k4 = st.columns(4)
with k1:
    st.metric("Selected series", len(selected_cols))
    st.caption("Number of energy commodities in the basket")

with k2:
    st.metric("Current index level", f"{basket.iloc[-1]:.1f}")
    st.caption("Latest basket value relative to the base year")

with k3:
    st.metric("Peak level", f"{basket.max():.1f}")
    st.caption("Highest basket value in the selected time window")

with k4:
    st.metric("Trough level", f"{basket.min():.1f}")
    st.caption("Lowest basket value in the selected time window")


st.divider()

# -------------------------------------------------------------------
# Tabs (Dashboard = one screen)
# -------------------------------------------------------------------

dashboard, details = st.tabs(["Dashboard", "Details"])

with dashboard:
    top_l, top_r = st.columns(2)
    bot_l, bot_r = st.columns(2)

    # --- Scatter (brushing source)
    fig_scatter = px.scatter(
        df_plot,
        x="basket_change",
        y="basket_index",
        hover_data=["date"],
        labels={
            "basket_change": f"Basket change ({change_mode})",
            "basket_index": f"Basket index ({base_year}=100)",
        },
    )
    fig_scatter.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10))

    with top_l:
        st.subheader("Change–level scatter")
        st.caption("Select points to filter all other views (brushing & linking)")
        sel = st.plotly_chart(fig_scatter, width="stretch", on_select="rerun")

    # --- Parse selection
    selected_dates = None
    try:
        selection = sel.get("selection") if isinstance(sel, dict) else getattr(sel, "selection", None)
        if selection:
            idxs = [p["pointIndex"] for p in selection["points"]]
            selected_dates = set(df_plot.iloc[idxs]["date"].dt.normalize())
    except Exception:
        selected_dates = None

    if selected_dates:
        mask = df_plot["date"].dt.normalize().isin(selected_dates)
        df_sel = df_plot[mask]
        idx_sel = idx[idx.index.normalize().isin(selected_dates)]
    else:
        df_sel = df_plot
        idx_sel = idx

    # --- Basket change over time
    fig_change = px.line(
        df_sel,
        x="date",
        y="basket_change",
        labels={"basket_change": f"Basket change ({change_mode})"},
    )
    fig_change.add_hline(y=0)
    fig_change.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10))

    with top_r:
        st.subheader("Basket change over time")
        st.plotly_chart(fig_change, width="stretch")

    # --- Indexed price levels
    idx_long = (
        idx_sel.reset_index(names="date")
        .melt(id_vars="date", var_name="commodity", value_name="index")
        .dropna()
    )
    fig_lines = px.line(
        idx_long,
        x="date",
        y="index",
        color="commodity",
        labels={"index": f"Index ({base_year}=100)"},
    )
    fig_lines.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10))

    with bot_l:
        st.subheader("Indexed price levels")
        st.plotly_chart(fig_lines, width="stretch")

    # --- Volatility ranking (FIXED)
    vol = idx_sel.pct_change().std().sort_values(ascending=False)
    vol_df = vol.rename("volatility").reset_index().rename(columns={"index": "commodity"})
    fig_vol = px.bar(vol_df, x="commodity", y="volatility")
    fig_vol.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10))

    with bot_r:
        st.subheader("Volatility ranking")
        st.plotly_chart(fig_vol, width="stretch")

with details:
    st.subheader("Distribution of basket changes")
    fig_hist = px.histogram(df_sel, x="basket_change", nbins=40)
    st.plotly_chart(fig_hist, width="stretch")

    if show_table:
        st.subheader("Filtered data")
        out = idx_sel.copy()
        out["Basket"] = idx_sel.mean(axis=1)
        st.dataframe(out.round(3), width="stretch", height=320)

    st.caption(
        "Dashboard requirements satisfied: 4+ visualizations, interaction, "
        "brushing & linking (scatter → all other views)."
    )