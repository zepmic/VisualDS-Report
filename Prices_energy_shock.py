import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Energy Shock Dashboard", layout="wide")
st.title("Energy shock dashboard (monthly commodity prices)")
st.caption(
    "Interactive dashboard with 4+ views and brushing & linking via Plotly selection. "
    "Base index: 2007 = 100. Data source: World Bank CMO Historical Data (Monthly)."
)


# -------------------------------------------------------------------
# 1) Load and clean the World Bank monthly commodity data
# -------------------------------------------------------------------

path = "CMO-Historical-Data-Monthly.xlsx"  # <- ggf. Pfad anpassen

raw = pd.read_excel(path, sheet_name="Monthly Prices")

meta_row = 5
data = raw.iloc[meta_row + 1:].copy()
codes_row = raw.iloc[meta_row].copy()

codes_row.iloc[0] = "DATE"
data.columns = codes_row.values

data = data.loc[:, ~pd.isna(data.columns)]
data = data.dropna(subset=["DATE"])

date_str = data["DATE"].astype(str)
date_clean = date_str.str.replace("M", "-", regex=False)
data["DATE"] = pd.to_datetime(date_clean, format="%Y-%m")
data = data.set_index("DATE").sort_index()

# -------------------------------------------------------------------
# Keep ONLY energy  
# -------------------------------------------------------------------

# Default energy codes known in the sheet
DEFAULT_ENERGY_CODES = ["CRUDE_BRENT", "NGAS_US", "COAL_AUS"]

# -------------------------------------------------------------------
# Build 2007=100 index
# -------------------------------------------------------------------

def make_index(df: pd.DataFrame, cols, base_start="2007-01-01", base_end="2007-12-31") -> pd.DataFrame:
    subset = df[list(cols)].apply(pd.to_numeric, errors="coerce")
    base_mask = (subset.index >= pd.to_datetime(base_start)) & (subset.index <= pd.to_datetime(base_end))
    base = subset.loc[base_mask].mean()
    idx = subset.divide(base).multiply(100)
    return idx

def yoy_pct(s: pd.Series) -> pd.Series:
    return s.pct_change(12).multiply(100)



with st.sidebar:
    st.header("Controls")

    # columns available
    all_series_cols = [c for c in data.columns if c != "DATE"]

    # prefer energy defaults if they exist
    available_defaults = [c for c in DEFAULT_ENERGY_CODES if c in all_series_cols]
    if not available_defaults:
        available_defaults = all_series_cols[:3]

    selected_cols = st.multiselect(
        "Select commodities (codes)",
        options=all_series_cols,
        default=available_defaults,
    )

    base_year = st.selectbox("Base year for index (100)", options=list(range(1960, 2025)), index=list(range(1960, 2025)).index(2007))
    base_start = f"{base_year}-01-01"
    base_end = f"{base_year}-12-31"

    start_plot = st.date_input("Start date", value=pd.to_datetime("2000-01-01").date())
    end_plot = st.date_input("End date", value=data.index.max().date())

    change_mode = st.radio("Change metric", ["YoY %", "MoM %"], index=0)

    show_table = st.checkbox("Show filtered data table", value=True)

# Guard against empty selection
if not selected_cols:
    st.warning("Please select at least one commodity series in the sidebar.")
    st.stop()

# -------------------------------------------------------------------
# Compute indices + series
# -------------------------------------------------------------------

idx_df = make_index(data, selected_cols, base_start=base_start, base_end=base_end)
idx_df = idx_df.loc[(idx_df.index >= pd.to_datetime(start_plot)) & (idx_df.index <= pd.to_datetime(end_plot))]

# Aggregate "Energy basket" as mean of selected commodities
basket = idx_df.mean(axis=1).rename("Basket")

if change_mode == "YoY %":
    basket_change = yoy_pct(basket).rename("Basket_change")
else:
    basket_change = mom_pct(basket).rename("Basket_change")

# -------------------------------------------------------------------
# Crisis windows (shading)
# -------------------------------------------------------------------

# -------------------------------------------------------------------
# Crisis windows
# -------------------------------------------------------------------

crisis_windows = {
    "GFC 2007–2009": ("2007-07-01", "2009-06-30"),
    "COVID 2020": ("2019-12-01", "2020-12-31"),
    "Inflation 2021–2023": ("2021-01-01", "2023-06-30"),
}

# -------------------------------------------------------------------
# Plot (only energy)
# -------------------------------------------------------------------

c1, c2, c3, c4 = st.columns(4)
c1.metric("Series selected", f"{len(selected_cols)}")
c2.metric("Last basket index", f"{basket.dropna().iloc[-1]:.1f}")
c3.metric("Peak basket index", f"{basket.max():.1f}")
c4.metric("Trough basket index", f"{basket.min():.1f}")

st.divider()


# Build a modeling table by date
df_plot = pd.DataFrame({
    "date": basket.index,
    "basket_index": basket.values,
    "basket_change": basket_change.values,
}).dropna()

st.subheader("Brushing & linking: select months in the scatter to filter other views")

scatter_x = "basket_change"
scatter_y = "basket_index"

fig_scatter = px.scatter(
    df_plot,
    x=scatter_x,
    y=scatter_y,
    hover_data={"date": True, "basket_change": ":.2f", "basket_index": ":.1f"},
    labels={
        "basket_change": f"Basket change ({change_mode})",
        "basket_index": f"Basket index ({base_year}=100)",
    },
)
fig_scatter.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))

# Selection event (brush)
sel = st.plotly_chart(fig_scatter, use_container_width=True, on_select="rerun")

selected_dates = None
try:
    if sel and isinstance(sel, dict) and "selection" in sel and sel["selection"] and "points" in sel["selection"]:
        pts = sel["selection"]["points"]
        # Plotly returns indices into df_plot
        idxs = [p.get("pointIndex") for p in pts if p.get("pointIndex") is not None]
        if idxs:
            selected_dates = set(df_plot.iloc[idxs]["date"].dt.normalize().tolist())
except Exception:
    selected_dates = None

if selected_dates:
    st.info(f"Selection active: {len(selected_dates)} month(s) selected. Clear the selection in the scatter (double-click) to reset.")
else:
    st.caption("No selection active — views show the full filtered date range.")

# Apply brushing filter to downstream views
if selected_dates:
    mask_sel = df_plot["date"].dt.normalize().isin(selected_dates)
    df_plot_sel = df_plot.loc[mask_sel].copy()
    idx_df_sel = idx_df.loc[idx_df.index.normalize().isin(selected_dates)].copy()
else:
    df_plot_sel = df_plot.copy()
    idx_df_sel = idx_df.copy()

st.divider()

# -------------------------------------------------------------------
# 4+ visualizations (dashboard grid)
# -------------------------------------------------------------------

left, right = st.columns(2)

# (1) Multi-line index time series (selected commodities)
with left:
    st.subheader("1) Indexed price levels (selected commodities)")
    idx_long = idx_df_sel.reset_index(names="date").melt(id_vars=["date"], var_name="commodity", value_name="index")
    fig_lines = px.line(
        idx_long.dropna(),
        x="date",
        y="index",
        color="commodity",
        labels={"index": f"Index ({base_year}=100)"},
    )
    # crisis shading
    for label, (s, e) in crisis_windows.items():
        fig_lines.add_vrect(
            x0=pd.to_datetime(s),
            x1=pd.to_datetime(e),
            opacity=0.12,
            line_width=0,
            annotation_text=label,
            annotation_position="top left",
        )
    fig_lines.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10), legend_title_text="Commodity")
    st.plotly_chart(fig_lines, use_container_width=True)

# (2) Basket change time series (YoY or MoM)
with right:
    st.subheader(f"2) Basket change over time ({change_mode})")
    fig_change = px.line(
        df_plot_sel,
        x="date",
        y="basket_change",
        labels={"basket_change": f"Basket change ({change_mode})"},
    )
    for label, (s, e) in crisis_windows.items():
        fig_change.add_vrect(
            x0=pd.to_datetime(s),
            x1=pd.to_datetime(e),
            opacity=0.12,
            line_width=0,
        )
    fig_change.add_hline(y=0, line_width=1)
    fig_change.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig_change, use_container_width=True)

left2, right2 = st.columns(2)

# (3) Distribution of changes (histogram)
with left2:
    st.subheader(f"3) Distribution of basket changes ({change_mode})")
    fig_hist = px.histogram(
        df_plot_sel,
        x="basket_change",
        nbins=40,
        labels={"basket_change": f"Basket change ({change_mode})"},
    )
    fig_hist.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig_hist, use_container_width=True)

# (4) Volatility ranking of selected commodities in the (possibly brushed) window
with right2:
    st.subheader("4) Volatility ranking (std of monthly returns)")
    # monthly returns from indexed series (equivalent to price returns)
    rets = idx_df_sel.pct_change(1)
    vol = rets.std(skipna=True).sort_values(ascending=False)
    vol_df = vol.rename("volatility").reset_index().rename(columns={"index": "commodity"})
    fig_bar = px.bar(vol_df, x="commodity", y="volatility", labels={"volatility": "Std (MoM returns)"})
    fig_bar.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)

# Optional: linked table view
if show_table:
    st.subheader("Filtered data (linked to selection)")
    out = idx_df_sel.copy()
    out["Basket"] = idx_df_sel.mean(axis=1)
    st.dataframe(out.round(3), use_container_width=True)

st.caption(
    "Notes: Sidebar controls are global filters. Brushing & linking is implemented via scatter selection; "
    "select months to update all other views and the table."
)