
import geopandas as gpd
import os
import osmnx as ox
import networkx as nx
from shapely.geometry import Point
import numpy as np
import math

VARIABLES_GPKG_PATH = "../data/VARIABLES_NEW.gpkg"
PARK_LAYER = "VARIABLES_base"
ID_COL = "group"

OUTPUT_PATH = r"/data/tycktill_output/network_analysis"
os.makedirs(OUTPUT_PATH, exist_ok=True)

SERVICE_AREAS_GPKG = f"{OUTPUT_PATH}\\service_area_of_parks.gpkg"
NETWORK_GPKG = f"{OUTPUT_PATH}\\walk_network.graphml"

TIME_CUTOFF = 600              # seconds = 10 minutes
WALK_SPEED_KPH = 5
EDGE_BUFFER = 25               # meters for polygonizing roads
BOUNDARY_SAMPLE_DISTANCE = 50  # meters between sampled access points

# ==================
# === load parks ===

parks = gpd.read_file(VARIABLES_GPKG_PATH, layer=PARK_LAYER)
parks_3006 = parks.to_crs(epsg=3006)
parks_wgs = parks.to_crs(epsg=4326)

print(parks.crs)
print(parks_3006.crs)
print(parks_wgs.crs)

#parks_buffered = parks_3006.buffer(2000)  # 2 km buffer (to later download fewer roads and reduce processing time)
#parks_buffered.to_file(r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\network_analysis\TESTS\parks_buffered.gpkg", driver="GPKG")

# ==================
# === study area ===

# Merge parks FIRST, then buffer once
study_area_3006 = parks_3006.union_all().buffer(2000)

# convert to WGS84 for OSMnx
study_area_poly = gpd.GeoSeries(
    [study_area_3006], crs=3006
).to_crs(epsg=4326).iloc[0]
#study_area = gpd.GeoSeries(parks_buffered, crs=3006)
#study_area = study_area.to_crs(epsg=4326).union_all()

# save study area
study_area_poly = study_area_3006  # result of union_all()
print(study_area_poly.is_valid)
study_area_gdf = gpd.GeoDataFrame(geometry=[study_area_poly], crs="EPSG:4326")
study_area_gdf.to_file(r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\network_analysis\TESTS\study_area.gpkg", driver="GPKG")



########################
# ox.settings.overpass_settings = '[out:json][timeout:180][maxsize:1073741824]'
#
# # use bbox instead because Bromma, Järva, etc are not getting included for some reason
# #minx, miny, maxx, maxy = study_area.bounds
# minx, miny, maxx, maxy = parks_wgs.total_bounds
# bbox = (maxy, miny, maxx, minx)  # (north, south, east, west)
#
# # buffer by degrees (wgs) instead om meters (ESPG: 3006)
# buffer_deg = 0.02
#
# bbox = (
#     maxy + buffer_deg,
#     miny - buffer_deg,
#     maxx + buffer_deg,
#     minx - buffer_deg
# )
########################

# ======================================
# === download walk network from OSM ===

#G = ox.graph_from_polygon(study_area, network_type="walk")
#G = ox.graph_from_bbox(
#    bbox,
#    network_type="walk"
#)

#G = ox.truncate_graph_polygon(G, study_area_poly)


###############
def download_graph_in_tiles(minx, miny, maxx, maxy, step=0.02):
    graphs = []

    x_vals = np.arange(minx, maxx, step)
    y_vals = np.arange(miny, maxy, step)

    total = len(x_vals) * len(y_vals)
    count = 0

    for x in x_vals:
        for y in y_vals:
            count += 1
            print(f"Downloading tile {count}/{total}")

            bbox = (
                y + step,  # north
                y,         # south
                x + step,  # east
                x          # west
            )

            try:
                G_tile = ox.graph_from_bbox(
                    bbox,
                    network_type="walk"
                )
                graphs.append(G_tile)

            except Exception as e:
                print(f"Tile failed: {e}")
                continue

    print("Merging graphs...")
    G = nx.compose_all(graphs)

    return G

# ==========================
# === LOAD OR DOWNLOAD ===

if os.path.exists(NETWORK_GPKG):
    print("Loading saved network...")
    G = ox.load_graphml(NETWORK_GPKG)

else:
    print("Downloading network (tile-based)...")

    minx, miny, maxx, maxy = parks_wgs.total_bounds

    G = download_graph_in_tiles(minx, miny, maxx, maxy, step=0.02)

    # Clip to study area
    G = ox.truncate_graph_polygon(G, study_area_poly)

    # Save for reuse
    ox.save_graphml(G, NETWORK_GPKG)
###############


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
            node, dist = ox.distance.nearest_nodes(
                G, pt.x, pt.y, return_dist=True
            )

            if dist < 150:
                nodes.append(node)

        except:
            continue

    # Remove duplicates
    nodes = list(set(nodes))

    if not nodes:
        return None

    # FAST: multi-source Dijkstra (ONE traversal)
    lengths = nx.multi_source_dijkstra_path_length(
        G,
        sources=nodes,
        cutoff=time_cutoff,
        weight="travel_time"
    )

    reachable_nodes = list(lengths.keys())

    if not reachable_nodes:
        return None

    subgraph = G.subgraph(reachable_nodes).copy()

    # Convert to undirected
    subgraph = ox.convert.to_undirected(subgraph)

    edges = ox.graph_to_gdfs(subgraph, nodes=False)

    # Project to meters
    edges_proj = edges.to_crs(epsg=3006)

    # Buffer
    polygon = edges_proj.buffer(EDGE_BUFFER).union_all()

    # Back to WGS84
    polygon = gpd.GeoSeries([polygon], crs=3006).to_crs(epsg=4326).iloc[0]

    return polygon

# =======================================
# === generate service areas of parks ===

service_geoms = []

#for idx, row in parks_wgs.iterrows():
for idx, row in parks_3006.iterrows():
    print(f"Processing park {idx + 1}/{len(parks)}")
    # try:
    #     # --- Work in projected CRS for sampling ---
    #     geom_3006 = row.geometry
    #     boundary_3006 = geom_3006.boundary
    #
    #     # Sample points in meters
    #     points_3006 = sample_boundary(boundary_3006, BOUNDARY_SAMPLE_DISTANCE)
    #
    #     if not points_3006:
    #         service_geoms.append(None)
    #         continue
    #
    #     # Convert sampled points to WGS84
    #     points_wgs = gpd.GeoSeries(points_3006, crs=3006).to_crs(epsg=4326)
    #
    #     # Generate isochrone
    #     iso = make_isochrone(G, points_wgs, TIME_CUTOFF)
    #
    #     service_geoms.append(iso)
    #
    # except Exception as e:
    #     print(f"Error processing park {idx}: {e}")
    #     service_geoms.append(None)

    try:
        boundary = row.geometry.boundary
        points_3006 = sample_boundary(boundary, BOUNDARY_SAMPLE_DISTANCE)

        if not points_3006:
            service_geoms.append(None)
            continue

        points_wgs = gpd.GeoSeries(points_3006, crs=3006).to_crs(epsg=4326)

        iso = make_isochrone(G, points_wgs, TIME_CUTOFF)
        service_geoms.append(iso)

    except Exception as e:
        print(f"Error processing park {idx}: {e}")
        service_geoms.append(None)

# ===========================
# === create output layer ===

# Create GeoDataFrame directly with correct CRS (WGS84!)
service_areas = gpd.GeoDataFrame(
    parks.drop(columns="geometry"),
    geometry=service_geoms,
    crs="EPSG:4326"
)

# Remove empty geometries
service_areas = service_areas[
    service_areas.geometry.notnull() & ~service_areas.geometry.is_empty
]

# back to EPSG:3006
service_areas = service_areas.to_crs(epsg=3006)

# ============
# === save ===

service_areas.to_file(SERVICE_AREAS_GPKG, layer="service_areas", driver="GPKG")
