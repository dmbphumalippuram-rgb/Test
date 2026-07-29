import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from shapely.geometry import Point, MultiPoint
from shapely.ops import voronoi_diagram

st.set_page_config(
    page_title="Confirmed Dengue Surveillance Intelligence",
    page_icon="🦟",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
[data-testid="stToolbar"], [data-testid="stHeaderActionElements"], #MainMenu, footer { display: none !important; visibility: hidden !important; }
header[data-testid="stHeader"] { background: transparent !important; pointer-events: none !important; }
[data-testid="stSidebarCollapsedControl"], [data-testid="stSidebarCollapseButton"] { display: flex !important; visibility: visible !important; pointer-events: auto !important; z-index: 999999 !important; }
div[data-testid="metric-container"] { background:#fff; border:1px solid #e2e8f0; padding:15px; border-radius:12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }
[data-testid="stMetricValue"] { font-size:28px !important; font-weight:700 !important; color: #1e293b !important; }
.header-container { background:linear-gradient(135deg, #7c2d12 0%, #b91c1c 100%); padding:24px; border-radius:14px; color:white; margin-bottom:20px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2); }
.header-title { font-size:30px; font-weight:800; margin: 0; }
.header-subtitle { color:#fca5a5; font-size: 15px; margin-top: 5px; }
.main { background-color: #f8f9fa; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="header-container">
        <div class="header-title">🦟 Confirmed Dengue Epidemiological Tracker</div>
        <div class="header-subtitle">Ernakulam District • Vector Density Risk & Anti-Larval Intervention Zones</div>
    </div>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    raw_data = {
        'Health Blocks': [
            'Angamaly', 'Chengamanad', 'Cheranalloor', 'Ezhikkara', 'Kalady',
            'Keechery', 'Kumbalanghi', 'Malayidamthuruth', 'Malippuram', 'Nettoor',
            'Pallarimangalam', 'Pampakuda', 'Pandappilly', 'Pizhala', 'Ramamangalam',
            'Vadavucode', 'Varappetty', 'Varappuzha', 'Vengoor', 'Kochi Corporation'
        ],
        'Number of Cases': [22, 13, 119, 21, 36, 62, 7, 70, 8, 10, 0, 7, 11, 3, 16, 24, 4, 76, 78, 110],
        'latitude': [10.1960, 10.1517, 10.0461, 10.1412, 10.1685, 9.8432, 9.8752, 10.0416, 10.0234, 9.9234, 10.0789, 9.8631, 9.8921, 10.0521, 9.8512, 9.9723, 10.0214, 10.0762, 10.1821, 9.9674],
        'longitude': [76.3860, 76.3685, 76.2891, 76.2185, 76.4385, 76.4321, 76.2845, 76.3985, 76.2189, 76.3124, 76.6821, 76.5412, 76.6214, 76.2412, 76.5812, 76.4412, 76.6512, 76.2612, 76.5512, 76.2426]
    }
    return pd.DataFrame(raw_data)

@st.cache_data
def generate_manual_district_boundaries(df):
    points = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
    multipoint = MultiPoint(points)
    district_boundary = multipoint.convex_hull.buffer(0.08)
    voronoi_regions = voronoi_diagram(multipoint, envelope=district_boundary.envelope)
    polygons = []
    for pt in points:
        for poly in voronoi_regions.geoms:
            clipped_poly = poly.intersection(district_boundary)
            if clipped_poly.contains(pt) or clipped_poly.touches(pt):
                polygons.append(clipped_poly)
                break
    gdf = gpd.GeoDataFrame(df, geometry=polygons, crs="EPSG:4326")
    gdf['centroid_lat'] = df['latitude']
    gdf['centroid_lon'] = df['longitude']
    return gdf

df_cases = load_data()
gdf_merged = generate_manual_district_boundaries(df_cases)

st.sidebar.header("🕹️ Controls & Filters")
map_style = st.sidebar.selectbox("Map Style:", ["CartoDB Positron", "CartoDB Dark Matter", "OpenStreetMap"], index=0)
hotspot_threshold = st.sidebar.slider("Vector Outbreak Threshold", min_value=5, max_value=100, value=30, step=5)

col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
total_cases = int(df_cases['Number of Cases'].sum())
total_blocks = len(df_cases)
hotspot_count = int((df_cases['Number of Cases'] > hotspot_threshold).sum())
max_row = df_cases.loc[df_cases['Number of Cases'].idxmax()]

col_kpi1.metric("Total Confirmed Dengue", f"{total_cases:,}")
col_kpi2.metric("Total Health Blocks", total_blocks)
col_kpi3.metric(f"High Vector Risk (>{hotspot_threshold})", hotspot_count, delta=f"{(hotspot_count/total_blocks)*100:.0f}% of district", delta_color="inverse")
col_kpi4.metric("Highest Outbreak Cluster", f"{max_row['Number of Cases']} Cases", delta=max_row['Health Blocks'], delta_color="off")

st.markdown("<br>", unsafe_allow_html=True)
left_col, right_col = st.columns([3, 2])
tile_mapping = {"CartoDB Dark Matter": "CartoDB dark_matter", "CartoDB Positron": "CartoDB positron", "OpenStreetMap": "OpenStreetMap"}

with left_col:
    st.subheader("🗺️ Dengue Density Map")
    m = folium.Map(location=[gdf_merged['centroid_lat'].mean(), gdf_merged['centroid_lon'].mean()], zoom_start=10, tiles=tile_mapping[map_style])
    choropleth = folium.Choropleth(
        geo_data=gdf_merged[['Health Blocks', 'Number of Cases', 'geometry']],
        data=gdf_merged, columns=["Health Blocks", "Number of Cases"],
        key_on="feature.properties.Health Blocks", fill_color="YlOrRd", fill_opacity=0.5,
        line_color="#444444", line_opacity=0.8, line_weight=1.5
    ).add_to(m)

    for _, row in gdf_merged.iterrows():
        lat, lon, cases, block_name = row['centroid_lat'], row['centroid_lon'], row['Number of Cases'], row['Health Blocks']
        is_hotspot = cases > hotspot_threshold
        color_code = "#D97706" if not is_hotspot else "#DC2626"
        fill_code = "#F59E0B" if not is_hotspot else "#EF4444"
        
        folium.CircleMarker(
            location=[lat, lon], radius=4 + (cases * 0.18), color=color_code, fill=True,
            fill_color=fill_code, fill_opacity=0.85 if is_hotspot else 0.45, weight=2 if is_hotspot else 1,
            tooltip=f"<b>{'⚠️ OUTBREAK ZONE: ' if is_hotspot else ''}{block_name}</b><br>Cases: {cases}"
        ).add_to(m)
    st_folium(m, width="100%", height=520)

with right_col:
    st.subheader("📊 Block Case Breakdown")
    search_query = st.text_input("🔍 Search Block", "")
    filtered_df = df_cases.copy()
    if search_query:
        filtered_df = filtered_df[filtered_df['Health Blocks'].str.contains(search_query, case=False)]
    if st.checkbox(f"Filter High Risk Only (>{hotspot_threshold} Cases)"):
        filtered_df = filtered_df[filtered_df['Number of Cases'] > hotspot_threshold]

    st.dataframe(
        filtered_df[['Health Blocks', 'Number of Cases']].sort_values(by="Number of Cases", ascending=False),
        column_config={"Health Blocks": st.column_config.TextColumn("Block Name"), "Number of Cases": st.column_config.ProgressColumn("Confirmed Cases", format="%d", min_value=0, max_value=int(df_cases['Number of Cases'].max()))},
        use_container_width=True, hide_index=True, height=430
    )
