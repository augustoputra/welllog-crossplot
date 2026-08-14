import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns

st.set_page_config(page_title="Well Log Crossplot Tool", layout="wide")

# ---- Load data once (cached so it doesn't re-read the file on every interaction) ----
FILE_PATH = 'database.xlsx'

@st.cache_data
def load_data(path):
    return pd.read_excel(path)

df_all = load_data(FILE_PATH)

well_list = sorted(df_all['WELL'].dropna().unique().tolist())
numeric_cols = df_all.select_dtypes(include='number').columns.tolist()
depth_min, depth_max = float(df_all['MD'].min()), float(df_all['MD'].max())

# ---- Fixed axis limits ----
# GR-RT crossplot
GR_MIN, GR_MAX = 0, 150
RT_MIN, RT_MAX = 1, 200
RT_FIXED_TICKS = [1, 10, 100, 200]

# NEU-DEN crossplot
NEU_MIN, NEU_MAX = -0.05, 0.45   # not inverted
DEN_MIN, DEN_MAX = 1.8, 2.9      # inverted

# ---- Generic lithology / porosity grid for the NEU-DEN crossplot ----
# Matrix points (zero-porosity end) and fluid point (100%-porosity end).
# Values are standard rock/fluid properties, not a copy of any vendor chart.
LITHOLOGY_MATRIX = {
    'Sandstone': {'rho_ma': 2.644, 'nphi_ma': -0.02, 'color': '#b8860b'},
    'Limestone': {'rho_ma': 2.706, 'nphi_ma': 0.00,  'color': '#1f6f8b'},
    'Dolomite':  {'rho_ma': 2.845, 'nphi_ma': 0.035, 'color': '#2e7d32'},
}
RHO_FLUID, NPHI_FLUID = 1.0, 1.0   # fresh-water/fluid point at 100% porosity
POROSITY_TICKS = np.arange(0.05, 0.46, 0.05)


def litho_point(rho_ma, nphi_ma, phi):
    """Point on a matrix-to-fluid porosity line at a given porosity fraction."""
    rhob = rho_ma * (1 - phi) + RHO_FLUID * phi
    nphi = nphi_ma * (1 - phi) + NPHI_FLUID * phi
    return nphi, rhob


def draw_lithology_grid(ax, phi_max=0.45):
    """Draw sandstone/limestone/dolomite matrix lines plus iso-porosity
    connector lines, mimicking a standard neutron-density lithology chart."""
    phi_line = np.linspace(0, phi_max, 100)

    # Matrix -> fluid fan lines
    for name, props in LITHOLOGY_MATRIX.items():
        nphi_vals, rhob_vals = zip(*[litho_point(props['rho_ma'], props['nphi_ma'], p) for p in phi_line])
        ax.plot(nphi_vals, rhob_vals, color=props['color'], lw=1.3, alpha=0.8, zorder=1)
        # Matrix point label at phi = 0
        ax.plot(props['nphi_ma'], props['rho_ma'], 'o', color=props['color'], ms=3, zorder=1)
        ax.annotate(f"{props['rho_ma']:.3f}", (props['nphi_ma'], props['rho_ma']),
                    textcoords="offset points", xytext=(-4, -4), fontsize=7,
                    color=props['color'], ha='right', va='top')

    # Iso-porosity connector lines across the three lithology lines
    order = ['Sandstone', 'Limestone', 'Dolomite']
    for phi in POROSITY_TICKS:
        pts = [litho_point(LITHOLOGY_MATRIX[n]['rho_ma'], LITHOLOGY_MATRIX[n]['nphi_ma'], phi) for n in order]
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color='gray', lw=0.6, alpha=0.6, zorder=1)
        # Label near the limestone (middle) point
        ax.annotate(f"{phi:.2f}", pts[1], textcoords="offset points", xytext=(2, 3),
                    fontsize=6.5, color='dimgray', zorder=1)


def draw_trend_arrows(ax):
    """Generic hydrocarbon/water trend arrows (illustrative, not tied to data)."""
    ax.annotate('', xy=(0.12, 2.20), xytext=(0.28, 2.05),
                arrowprops=dict(arrowstyle='-|>', color='red', lw=2))
    ax.text(0.15, 2.15, 'HC Trend', color='red', fontsize=9, rotation=-30,
            ha='center', va='center', fontweight='bold')

    ax.annotate('', xy=(0.34, 2.10), xytext=(0.20, 2.28),
                arrowprops=dict(arrowstyle='-|>', color='blue', lw=2))
    ax.text(0.31, 2.16, 'Water Trend', color='blue', fontsize=9, rotation=-30,
            ha='center', va='center', fontweight='bold')


def pick_default(candidates, fallback):
    for c in candidates:
        if c in numeric_cols:
            return c
    return fallback


st.title("Well Log Crossplot Tool")

# =========================================================
# Sidebar — well selection & depth ranges
# =========================================================
st.sidebar.header("Well Selection")

analyze_wells = st.sidebar.multiselect("Analyze wells", well_list)
reference_wells = st.sidebar.multiselect("Reference wells", well_list)

st.sidebar.subheader("Analyze depth range")
col_a1, col_a2 = st.sidebar.columns(2)
top_a = col_a1.number_input("Top", min_value=depth_min, max_value=depth_max,
                             value=depth_min, step=1.0, key="analyze_top")
bott_a = col_a2.number_input("Bottom", min_value=depth_min, max_value=depth_max,
                              value=depth_max, step=1.0, key="analyze_bottom")
if top_a > bott_a:
    top_a, bott_a = bott_a, top_a

st.sidebar.subheader("Reference well depth ranges")
reference_ranges = {}
for well in reference_wells:
    well_depths = df_all.loc[df_all['WELL'] == well, 'MD']
    w_min, w_max = float(well_depths.min()), float(well_depths.max())
    st.sidebar.markdown(f"**{well}**")
    col_r1, col_r2 = st.sidebar.columns(2)
    top_r = col_r1.number_input(f"{well} top", min_value=w_min, max_value=w_max,
                                 value=w_min, step=1.0, key=f"{well}_top")
    bott_r = col_r2.number_input(f"{well} bottom", min_value=w_min, max_value=w_max,
                                  value=w_max, step=1.0, key=f"{well}_bottom")
    if top_r > bott_r:
        top_r, bott_r = bott_r, top_r
    reference_ranges[well] = (top_r, bott_r)

# =========================================================
# Tabs — one per plot type
# =========================================================
tab1, tab2 = st.tabs(["GR-RT Crossplot", "NEU-DEN Crossplot"])

# ---------------------------------------------------------
# GR-RT Crossplot (fixed scale: X = GR 0-150, Y = RT log10 up to 200)
# ---------------------------------------------------------
with tab1:
    gr_col = pick_default(['GR', 'GAMMA', 'Gamma'], numeric_cols[0])
    rt_col = pick_default(['RT'], numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0])

    st.caption(f"Using columns — X: **{gr_col}**, Y: **{rt_col}**")

    if st.button("Plot GR-RT Crossplot", type="primary"):
        if not analyze_wells and not reference_wells:
            st.warning("Please select at least one well (Analyze or Reference).")
        else:
            fig, ax = plt.subplots(figsize=(12, 8))

            analyze_palette = sns.color_palette("dark", len(analyze_wells))
            reference_palette = sns.color_palette("colorblind", len(reference_wells))

            for well, color in zip(analyze_wells, analyze_palette):
                sub = df_all[(df_all['WELL'] == well) &
                             (df_all['MD'] >= top_a) & (df_all['MD'] <= bott_a)]
                sns.scatterplot(data=sub, x=gr_col, y=rt_col, ax=ax,
                                 label=f'{well} (analyze)', color=color, s=25, alpha=1.0,
                                 edgecolor='black', linewidth=0.4, zorder=3)

            for well, color in zip(reference_wells, reference_palette):
                top_r, bott_r = reference_ranges[well]
                sub = df_all[(df_all['WELL'] == well) &
                             (df_all['MD'] >= top_r) & (df_all['MD'] <= bott_r)]
                sns.scatterplot(data=sub, x=gr_col, y=rt_col, ax=ax,
                                 label=f'{well} (ref {top_r:.0f}-{bott_r:.0f})',
                                 color=color, s=40, alpha=0.75, marker='x', linewidth=1.2, zorder=2)

            # Fixed X axis: GR 0-150
            ax.set_xlim(GR_MIN, GR_MAX)

            # Fixed Y axis: RT log10, up to 200
            ax.set_yscale('log')
            ax.set_ylim(RT_MIN, RT_MAX)
            ax.set_yticks(RT_FIXED_TICKS)
            ax.yaxis.set_major_formatter(mticker.ScalarFormatter())
            ax.yaxis.set_minor_formatter(mticker.NullFormatter())

            ax.set_title(f'GR-RT Crossplot ({rt_col} vs {gr_col})')
            ax.set_xlabel(gr_col)
            ax.set_ylabel(rt_col + ' (log)')
            ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
            ax.grid(True, which='both', alpha=0.3)
            fig.tight_layout()
            st.pyplot(fig)

# ---------------------------------------------------------
# NEU-DEN Crossplot (fixed scale: NEU -0.05 to 0.45 not inverted,
# DEN 1.8 to 2.9 inverted)
# ---------------------------------------------------------
with tab2:
    neu_col = pick_default(['NEU', 'NPHI', 'NEUT', 'PHIN'], numeric_cols[0])
    den_col = pick_default(['DEN', 'RHOB', 'RHOZ'],
                            numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0])

    st.caption(f"Using columns — X: **{neu_col}**, Y: **{den_col}**")

    gc1, gc2 = st.columns(2)
    show_grid = gc1.checkbox("Show lithology porosity grid", value=True)
    show_arrows = gc2.checkbox("Show HC/Water trend arrows", value=False)

    if st.button("Plot NEU-DEN Crossplot", type="primary"):
        if not analyze_wells and not reference_wells:
            st.warning("Please select at least one well (Analyze or Reference).")
        else:
            fig, ax = plt.subplots(figsize=(10, 9))

            analyze_palette = sns.color_palette("dark", len(analyze_wells))
            reference_palette = sns.color_palette("colorblind", len(reference_wells))

            for well, color in zip(analyze_wells, analyze_palette):
                sub = df_all[(df_all['WELL'] == well) &
                             (df_all['MD'] >= top_a) & (df_all['MD'] <= bott_a)]
                sns.scatterplot(data=sub, x=neu_col, y=den_col, ax=ax,
                                 label=f'{well} (analyze)', color=color, s=25, alpha=1.0,
                                 edgecolor='black', linewidth=0.4, zorder=3)

            for well, color in zip(reference_wells, reference_palette):
                top_r, bott_r = reference_ranges[well]
                sub = df_all[(df_all['WELL'] == well) &
                             (df_all['MD'] >= top_r) & (df_all['MD'] <= bott_r)]
                sns.scatterplot(data=sub, x=neu_col, y=den_col, ax=ax,
                                 label=f'{well} (ref {top_r:.0f}-{bott_r:.0f})',
                                 color=color, s=40, alpha=0.75, marker='x', linewidth=1.2, zorder=2)

            if show_grid:
                draw_lithology_grid(ax)
            if show_arrows:
                draw_trend_arrows(ax)

            # Fixed axis scale for NEU-DEN crossplot
            ax.set_xlim(NEU_MIN, NEU_MAX)          # NEU: not inverted
            ax.set_ylim(DEN_MAX, DEN_MIN)           # DEN: inverted

            ax.set_title(f'NEU-DEN Crossplot ({den_col} vs {neu_col})')
            ax.set_xlabel(neu_col)
            ax.set_ylabel(den_col + ' (inverted)')
            ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
            ax.grid(True, which='both', alpha=0.3)
            fig.tight_layout()
            st.pyplot(fig)
