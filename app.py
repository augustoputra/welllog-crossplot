import streamlit as st
import pandas as pd
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

RT_FIXED_TICKS = [1, 10, 100, 1000]

# ---- Fixed axis limits ----
GR_MAX = 150

NEU_MIN, NEU_MAX = -0.15, 0.45
DEN_MIN, DEN_MAX = 1.9, 2.9


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
tab1, tab2 = st.tabs(["Generic Crossplot", "NEU-DEN Crossplot"])

# ---------------------------------------------------------
# Generic Crossplot
# ---------------------------------------------------------
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    x_col = c1.selectbox("X axis", numeric_cols,
                          index=numeric_cols.index('RT') if 'RT' in numeric_cols else 0)
    y_col = c2.selectbox("Y axis", numeric_cols,
                          index=numeric_cols.index('GR') if 'GR' in numeric_cols else 1)
    x_log = c3.checkbox("X axis log scale", value=True)
    y_log = c4.checkbox("Y axis log scale", value=False)

    if st.button("Plot Crossplot", type="primary"):
        if not analyze_wells and not reference_wells:
            st.warning("Please select at least one well (Analyze or Reference).")
        else:
            fig, ax = plt.subplots(figsize=(12, 8))

            analyze_palette = sns.color_palette("dark", len(analyze_wells))
            reference_palette = sns.color_palette("colorblind", len(reference_wells))

            for well, color in zip(analyze_wells, analyze_palette):
                sub = df_all[(df_all['WELL'] == well) &
                             (df_all['MD'] >= top_a) & (df_all['MD'] <= bott_a)]
                sns.scatterplot(data=sub, x=x_col, y=y_col, ax=ax,
                                 label=f'{well} (analyze)', color=color, s=25, alpha=1.0,
                                 edgecolor='black', linewidth=0.4, zorder=3)

            for well, color in zip(reference_wells, reference_palette):
                top_r, bott_r = reference_ranges[well]
                sub = df_all[(df_all['WELL'] == well) &
                             (df_all['MD'] >= top_r) & (df_all['MD'] <= bott_r)]
                sns.scatterplot(data=sub, x=x_col, y=y_col, ax=ax,
                                 label=f'{well} (ref {top_r:.0f}-{bott_r:.0f})',
                                 color=color, s=40, alpha=0.75, marker='x', linewidth=1.2, zorder=2)

            if x_log:
                ax.set_xscale('log')
                ax.set_xlim(RT_FIXED_TICKS[0], RT_FIXED_TICKS[-1])
                ax.set_xticks(RT_FIXED_TICKS)
                ax.xaxis.set_major_formatter(mticker.ScalarFormatter())
                ax.xaxis.set_minor_formatter(mticker.NullFormatter())

            # Cap the Y axis at GR_MAX whenever GR is plotted on the Y axis
            if y_col.upper() == 'GR':
                if y_log:
                    ax.set_yscale('log')
                    ax.set_ylim(1, GR_MAX)
                else:
                    ax.set_ylim(0, GR_MAX)
            elif y_log:
                ax.set_yscale('log')

            ax.set_title(f'Crossplot of {y_col} vs {x_col}')
            ax.set_xlabel(x_col + (' (log)' if x_log else ''))
            ax.set_ylabel(y_col + (' (log)' if y_log else ''))
            ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
            ax.grid(True, which='both', alpha=0.3)
            fig.tight_layout()
            st.pyplot(fig)

# ---------------------------------------------------------
# NEU-DEN Crossplot
# ---------------------------------------------------------
with tab2:
    neu_default = pick_default(['NPHI', 'NEU', 'NEUT', 'PHIN'], numeric_cols[0])
    den_default = pick_default(['RHOB', 'DEN', 'RHOZ'],
                                numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0])

    c1, c2, c3, c4 = st.columns(4)
    neu_col = c1.selectbox("NEU col", numeric_cols, index=numeric_cols.index(neu_default))
    den_col = c2.selectbox("DEN col", numeric_cols, index=numeric_cols.index(den_default))
    neu_invert = c3.checkbox("Invert NEU axis (standard convention)", value=True)
    den_invert = c4.checkbox("Invert DEN axis", value=True)

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

            # Fixed axis scale for NEU-DEN crossplot
            if neu_invert:
                ax.set_xlim(NEU_MAX, NEU_MIN)
            else:
                ax.set_xlim(NEU_MIN, NEU_MAX)

            if den_invert:
                ax.set_ylim(DEN_MAX, DEN_MIN)
            else:
                ax.set_ylim(DEN_MIN, DEN_MAX)

            ax.set_title(f'NEU-DEN Crossplot ({den_col} vs {neu_col})')
            ax.set_xlabel(neu_col + (' (inverted)' if neu_invert else ''))
            ax.set_ylabel(den_col + (' (inverted)' if den_invert else ''))
            ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left')
            ax.grid(True, which='both', alpha=0.3)
            fig.tight_layout()
            st.pyplot(fig)
