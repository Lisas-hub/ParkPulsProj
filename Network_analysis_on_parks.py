
import geopandas as gpd
import os
import osmnx as ox
import networkx as nx
from shapely.geometry import Point
import numpy as np

VARIABLES_GPKG_PATH = "data/VARIABLES_NEW.gpkg"
PARK_LAYER = "VARIABLES_base"
ID_COL = "group"

OUTPUT_PATH = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\network_analysis"
os.makedirs(OUTPUT_PATH, exist_ok=True)
SERVICE_AREAS_GPKG = f"{OUTPUT_PATH}\\service_area_of_parks.gpkg"
NETWORK_GPKG = f"{OUTPUT_PATH}\\walk_network.gpkg"

TIME_CUTOFF = 600              # seconds = 10 minutes
WALK_SPEED_KPH = 5
EDGE_BUFFER = 25               # meters for polygonizing roads
BOUNDARY_SAMPLE_DISTANCE = 50  # meters between sampled access points

# ==================
# === load parks ===

parks = gpd.read_file(VARIABLES_GPKG_PATH, layer=PARK_LAYER)
parks_3006 = parks.to_crs(epsg=3006)  # important for OSMnx
parks_buffered = parks_3006.buffer(2000)  # 2 km buffer (to later download fewer roads and reduce processing time)

# convert to WGS84 for OSMnx
study_area = gpd.GeoSeries(parks_buffered, crs=3006)
study_area = study_area.to_crs(epsg=4326).union_all()

# convert to WGS84 for OSMnx
parks_wgs = parks.to_crs(epsg=4326)

# ======================================
# === download walk network from OSM ===

G = ox.graph_from_polygon(study_area, network_type="walk")

# =====================================
# === add travel time to park edges ===

for u, v, k, data in G.edges(keys=True, data=True):
    data["speed_kph"] = WALK_SPEED_KPH
    data["travel_time"] = data["length"] / (WALK_SPEED_KPH * 1000 / 3600)

# =============================
# === save network for QGIS ===

nodes, edges = ox.graph_to_gdfs(G)

edges.to_file(NETWORK_GPKG, layer="edges", driver="GPKG")
nodes.to_file(NETWORK_GPKG, layer="nodes", driver="GPKG")

# ===========================================
# === sample points along park boundaries ===

def sample_boundary(geom, spacing):
    length = geom.length
    distances = np.arange(0, length, spacing)
    points = [geom.interpolate(d) for d in distances]
    return points

# =============================================
# === get service area per park (isochrone) ===

def make_isochrone(G, points, time_cutoff):
    nodes = []

    for pt in points:
        try:
            node = ox.distance.nearest_nodes(G, pt.x, pt.y)
            nodes.append(node)
        except:
            continue

    subgraph = nx.Graph()

    for node in nodes:
        ego = nx.ego_graph(G, node, radius=time_cutoff, distance="travel_time")
        subgraph = nx.compose(subgraph, ego)

    if len(subgraph.nodes) == 0:
        return None

    _, edges = ox.graph_to_gdfs(subgraph)

    polygon = edges.buffer(EDGE_BUFFER).union_all()

    return polygon

# =======================================
# === generate service areas of parks ===

service_geoms = []

for idx, row in parks_wgs.iterrows():
    boundary = row.geometry.boundary

    # sample points along boundary
    points = sample_boundary(boundary, spacing=0.0005)  # ~50m in lat/lon

    iso = make_isochrone(G, points, TIME_CUTOFF)
    service_geoms.append(iso)

# ===========================
# === create output layer ===

service_areas = parks_wgs.copy()
service_areas["geometry"] = service_geoms

# back to EPSG:3006
service_areas = service_areas.to_crs(epsg=3006)

# ============
# === save ===

service_areas.to_file(SERVICE_AREAS_GPKG, layer="service_areas", driver="GPKG")
