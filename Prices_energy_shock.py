import pandas as pd
import matplotlib.pyplot as plt

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

energy_codes = ["CRUDE_BRENT", "NGAS_US", "COAL_AUS"]

# -------------------------------------------------------------------
# Build 2007=100 index
# -------------------------------------------------------------------

def make_index(data, cols, base_start="2007-01-01", base_end="2007-12-31"):
    subset = data[cols].apply(pd.to_numeric, errors="coerce")
    base_mask = (subset.index >= base_start) & (subset.index <= base_end)
    base = subset.loc[base_mask].mean()
    idx = subset / base * 100
    return idx

energy_idx = make_index(data, energy_codes)
energy_series = energy_idx.mean(axis=1)

start_plot = "2000-01-01"
energy_series = energy_series.loc[start_plot:]

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

plt.style.use("default")
fig, ax = plt.subplots(figsize=(12, 4))

ax.plot(energy_series.index, energy_series.values, label="Energy (Brent, gas, coal)")
ax.set_ylabel("Index (2007 = 100)")
ax.set_title("Energy (Brent, gas, coal)")
ax.axhline(100, linestyle="--", linewidth=0.8)

# Shade crisis periods
for label, (start, end) in crisis_windows.items():
    ax.axvspan(pd.to_datetime(start),
               pd.to_datetime(end),
               alpha=0.1)
    ax.text(pd.to_datetime(start),
            ax.get_ylim()[0] + 0.02*(ax.get_ylim()[1]-ax.get_ylim()[0]),
            label.split()[0], fontsize=8, rotation=90, alpha=0.7)

ax.legend(loc="upper left")
ax.set_xlabel("Date")

fig.suptitle("Crisis behaviour of energy commodities (2007 = 100)", fontsize=14)
fig.tight_layout(rect=[0, 0, 1, 0.94])

plt.show()