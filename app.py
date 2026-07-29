import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point, MultiPoint
from shapely.ops import voronoi_diagram, nearest_points

# ==============================================================================
# 1. PAGE CONFIGURATION & STYLING (banner/menu NOT hidden — kept visible)
# ==============================================================================
st.set_page_config(
    page_title="Confirmed Dengue Surveillance Intelligence",
    page_icon="🦟",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        .main { background-color: #f8f9fa; }
        [data-testid="stMetricValue"] {
            font-size: 28px !important;
            font-weight: 700 !important;
            color: #1e293b !important;
        }
        div[data-testid="metric-container"] {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            padding: 15px 20px;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }
        .header-container {
            background: linear-gradient(135deg, #7c2d12 0%, #b91c1c 100%);
            padding: 24px;
            border-radius: 14px;
            color: white;
            margin-bottom: 25px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2);
        }
        .header-title { font-size: 30px; font-weight: 800; margin: 0; }
        .header-subtitle { font-size: 15px; color: #fca5a5; margin-top: 5px; }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="header-container">
        <div class="header-title">🦟 Confirmed Dengue Epidemiological Tracker</div>
        <div class="header-subtitle">Ernakulam District • Vector Density Risk & Anti-Larval Intervention Zones</div>
    </div>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CONFIRMED DENGUE DATA & AUTOMATIC BOUNDARY GENERATOR
# ==============================================================================
@st.cache_data
def load_data():
    raw_data = {
        'Health Blocks': [
            'Angamaly', 'Chengamanad', 'Cheranalloor', 'Ezhikkara', 'Kalady',
            'Keechery', 'Kumbalanghi', 'Malayidamthuruth', 'Malippuram', 'Nettoor',
            'Pallarimangalam', 'Pampakuda', 'Pandappilly', 'Pizhala', 'Ramamangalam',
            'Vadavucode', 'Varappetty', 'Varappuzha', 'Vengoor', 'Kochi Corporation'
        ],
        'Number of Cases': [
            22, 13, 119, 21, 36, 62, 7, 70, 8, 10, 0, 7, 11, 3, 16, 24, 4, 76, 78, 110
        ],
        'latitude': [
            10.1960, 10.1517, 10.0461, 10.1412, 10.1685,
            9.8432, 9.8752, 10.0416, 10.0234, 9.9234,
            10.0789, 9.8631, 9.8921, 10.0521, 9.8512,
            9.9723, 10.0214, 10.0762, 10.1821, 9.9674
        ],
        'longitude': [
            76.3860, 76.3685, 76.2891, 76.2185, 76.4385,
            76.4321, 76.2845, 76.3985, 76.2189, 76.3124,
            76.6821, 76.5412, 76.6214, 76.2412, 76.5812,
            76.4412, 76.6512, 76.2612, 76.5512, 76.2426
        ]
    }
    return pd.DataFrame(raw_data)


@st.cache_data
def generate_manual_district_boundaries(df):
    """Generates contiguous dynamic spatial polygons around health block centroids.

    Fix: the original version matched each point to a Voronoi cell using only
    `contains`/`touches`, which can fail for points that sit exactly on a
    cell boundary after clipping (a floating-point precision issue). That
    silently produced fewer polygons than points, which crashes
    GeoDataFrame construction. This version guarantees exactly one polygon
    per point by falling back to a small buffer check, and finally to
    nearest-polygon-by-distance so a match is always found.
    """
    points = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
    multipoint = MultiPoint(points)

    district_boundary = multipoint.convex_hull.buffer(0.08)
    voronoi_regions = voronoi_diagram(multipoint, envelope=district_boundary.envelope)

    clipped_cells = [poly.intersection(district_boundary) for poly in voronoi_regions.geoms]

    polygons = []
    for pt in points:
        match = None
        # Pass 1: exact containment/touch
        for cell in clipped_cells:
            if cell.contains(pt) or cell.touches(pt):
                match = cell
                break
        # Pass 2: tiny buffer tolerance for boundary precision issues
        if match is None:
            for cell in clipped_cells:
                if cell.buffer(1e-9).contains(pt):
                    match = cell
                    break
        # Pass 3: fall back to nearest cell by distance (guarantees a match)
        if match is None:
            match = min(clipped_cells, key=lambda cell: pt.distance(cell))
        polygons.append(match)

    gdf = gpd.GeoDataFrame(df, geometry=polygons, crs="EPSG:4326")
    gdf['centroid_lat'] = df['latitude']
    gdf['centroid_lon'] = df['longitude']
    return gdf


df_cases = load_data()
gdf_merged = generate_manual_district_boundaries(df_cases)

# ==============================================================================
# 3. SIDEBAR CONTROLS
# ==============================================================================
st.sidebar.header("🕹️ Map Controls & Filters")

map_style = st.sidebar.selectbox(
    "Choose Map Base Layer Style:",
    options=["CartoDB Positron", "CartoDB Dark Matter", "OpenStreetMap"],
    index=0
)

hotspot_threshold = st.sidebar.slider(
    "Vector Outbreak Threshold",
    min_value=5,
    max_value=100,
    value=30,
    step=5,
    help="Blocks with confirmed Dengue cases above this limit are flagged as high risk."
)

# ==============================================================================
# 4. KPI SUMMARY CARDS
# ==============================================================================
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

total_cases = int(df_cases['Number of Cases'].sum())
total_blocks = len(df_cases)
hotspot_count = int((df_cases['Number of Cases'] > hotspot_threshold).sum())
max_row = df_cases.loc[df_cases['Number of Cases'].idxmax()]

col_kpi1.metric("Total Confirmed Dengue", f"{total_cases:,}")
col_kpi2.metric("Total Health Blocks", total_blocks)
col_kpi3.metric(
    f"High Vector Risk (>{hotspot_threshold})",
    hotspot_count,
    delta=f"{(hotspot_count / total_blocks) * 100:.0f}% of district",
    delta_color="inverse"
)
col_kpi4.metric(
    "Highest Outbreak Cluster",
    f"{max_row['Number of Cases']} Cases",
    delta=max_row['Health Blocks'],
    delta_color="off"
)

st.markdown("<br>", unsafe_allow_html=True)

# ==============================================================================
# 5. SIDE-BY-SIDE MAIN LAYOUT
# ==============================================================================
left_col, right_col = st.columns([3, 2])

tile_mapping = {
    "CartoDB Dark Matter": "CartoDB dark_matter",
    "CartoDB Positron": "CartoDB positron",
    "OpenStreetMap": "OpenStreetMap"
}

with left_col:
    st.subheader("🗺️ Dengue Density Map")

    m = folium.Map(
        location=[gdf_merged['centroid_lat'].mean(), gdf_merged['centroid_lon'].mean()],
        zoom_start=10,
        tiles=tile_mapping[map_style]
    )

    # Choropleth base layer
    choropleth = folium.Choropleth(
        geo_data=gdf_merged[['Health Blocks', 'Number of Cases', 'geometry']],
        name="Choropleth Intensity",
        data=gdf_merged,
        columns=["Health Blocks", "Number of Cases"],
        key_on="feature.properties.Health Blocks",
        fill_color="YlOrRd",
        fill_opacity=0.5,
        line_color="#444444",
        line_opacity=0.8,
        line_weight=1.5,
        highlight=True
    ).add_to(m)

    # Restored from file 1: tooltip on the choropleth polygons themselves
    choropleth.geojson.add_child(
        folium.features.GeoJsonTooltip(
            fields=["Health Blocks", "Number of Cases"],
            aliases=["Health Block:", "Confirmed Dengue Cases:"],
            style="font-family: sans-serif; font-size: 12px; padding: 6px;"
        )
    )

    # Hotspot Circles
    for _, row in gdf_merged.iterrows():
        lat = row['centroid_lat']
        lon = row['centroid_lon']
        cases = row['Number of Cases']
        block_name = row['Health Blocks']
        is_hotspot = cases > hotspot_threshold

        color_code = "#D97706" if not is_hotspot else "#DC2626"
        fill_code = "#F59E0B" if not is_hotspot else "#EF4444"

        folium.CircleMarker(
            location=[lat, lon],
            radius=4 + (cases * 0.18),
            color=color_code,
            fill=True,
            fill_color=fill_code,
            fill_opacity=0.85 if is_hotspot else 0.45,
            weight=2 if is_hotspot else 1,
            tooltip=f"<b>{'⚠️ OUTBREAK ZONE: ' if is_hotspot else ''}{block_name}</b><br>Cases: {cases}",
            # Restored from file 1: rich HTML popup
            popup=folium.Popup(
                f"<div style='font-family: sans-serif; min-width: 140px;'>"
                f"<h4 style='margin:0; color:{color_code};'>{block_name}</h4>"
                f"<hr style='margin:6px 0; border:0; border-top:1px solid #ccc;'>"
                f"<b>Status:</b> {'⚠️ High Risk Zone' if is_hotspot else '✅ Moderate/Low Risk'}<br>"
                f"<b>Confirmed Cases:</b> <span style='font-size:14px; font-weight:bold;'>{cases}</span>"
                f"</div>",
                max_width=250
            )
        ).add_to(m)

    # Bug fix: add a layer control so the named Choropleth layer is actually usable
    folium.LayerControl().add_to(m)

    st_folium(m, width="100%", height=520)

with right_col:
    st.subheader("📊 Block Case Breakdown")

    search_query = st.text_input("🔍 Search Health Block", "")

    filtered_df = df_cases.copy()
    if search_query:
        # Bug fix: regex=False so special characters like ( ) . + * don't
        # raise errors or produce unintended regex matches
        filtered_df = filtered_df[
            filtered_df['Health Blocks'].str.contains(search_query, case=False, regex=False)
        ]

    show_hotspots_only = st.checkbox(f"Filter High Risk Only (>{hotspot_threshold} Cases)")
    if show_hotspots_only:
        filtered_df = filtered_df[filtered_df['Number of Cases'] > hotspot_threshold]

    st.dataframe(
        filtered_df[['Health Blocks', 'Number of Cases']].sort_values(by="Number of Cases", ascending=False),
        column_config={
            "Health Blocks": st.column_config.TextColumn("Health Block Name"),
            "Number of Cases": st.column_config.ProgressColumn(
                "Confirmed Cases",
                help="Total laboratory-confirmed Dengue cases",
                format="%d",
                min_value=0,
                max_value=int(df_cases['Number of Cases'].max())
            )
        },
        use_container_width=True,
        hide_index=True,
        height=430
    )
