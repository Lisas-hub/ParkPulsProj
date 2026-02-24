
import os
import numpy as np
import geopandas as gpd
from sklearn.neighbors import KernelDensity
from scipy.ndimage import gaussian_filter
import rasterio
from rasterio.transform import from_origin
from rasterio.mask import mask
import pandas as pd


points_path = r"C:/Users/lisajos/PycharmProjects/park_proj/data/tycktill_output/BERTopic_filtered/tycktill_filtered.gpkg"
points_layername = "pts_in_parks_with_topics"

boundary_path = r"C:/Users/lisajos/QGIS_Projects/Output/Stadsdelsomraden_Stadskartan.gpkg"
boundary_layername = "stadsdelsnmnder"

output_folder = r"C:\Users\lisajos\PycharmProjects\park_proj\data\qgis_maps\TIFFs\FINAL"
os.makedirs(output_folder, exist_ok=True)


# =========
# load data

points = gpd.read_file(points_path, layer=points_layername)
boundary = gpd.read_file(boundary_path, layer=boundary_layername)

if points.crs != boundary.crs:
    points = points.to_crs(boundary.crs)

points["Inkommet datum"] = pd.to_datetime(
    points["Inkommet datum"],
    format="mixed",
    errors="coerce"
)

# KDE parameters
radius_m = 450        # KDE bandwidth in meters
pixel_size = 50       # pixel size in meters
nodata_val = -9999.0

topics_to_map = {    # *** använd meta-topics istället? ***
    "Praise": {
        "bastu_bastun_sauna": [600],
        "blommor_tulpaner_påskliljor": [457],
        "cykelbanan_cykelbana_asfalteringen": [485],
        "snöröjningen_beröm_tack": [136],
        "lekgatan, lekgata, barnen": [131],
    },
    "Ideas": {
        "cyklisterna_cykelbanan_cykelbana": [5],
        "parkeringsplatser_boendeparkering_parkerar": [15],
        "köer_lindhagensgatan_trafiken": [254],
    },
    "Error_Complaints": {
        "klotter_klotters_hammarbyklotter": [1],
        "översvämning_vattenansamling_vattensamling": [0],
    }
}

categories = {
    "Praise": ["Beröm"],
    "Ideas": ["Idé"],
    "Error_Complaints": ["Felanmälan", "Klagomål"]
}

# =============
# KDE FUNCTIONS

def create_kde_raster(points_gdf, boundary_gdf, radius_m, pixel_size):

    coords = np.array([(pt.x, pt.y) for pt in points_gdf.geometry])

    if len(coords) == 0:
        return None, None, None

    minx, miny, maxx, maxy = boundary_gdf.total_bounds

    x_grid = np.arange(minx, maxx + pixel_size, pixel_size)
    y_grid = np.arange(maxy, miny - pixel_size, -pixel_size)

    X, Y = np.meshgrid(x_grid, y_grid)
    grid_coords = np.vstack([X.ravel(), Y.ravel()]).T

    kde = KernelDensity(bandwidth=radius_m, kernel="gaussian")
    kde.fit(coords)

    Z_raw = np.exp(kde.score_samples(grid_coords)).reshape(X.shape)

    # convert to intensity (MATCH CATEGORY SCRIPT)
    Z_raw = Z_raw * len(coords)

    transform = from_origin(minx, maxy, pixel_size, pixel_size)

    return Z_raw, transform, Z_raw.shape

def mask_array_to_boundary(Z, transform, boundary_gdf):

    with rasterio.io.MemoryFile() as memfile:

        meta = {
            "driver": "GTiff",
            "height": Z.shape[0],
            "width": Z.shape[1],
            "count": 1,
            "dtype": "float32",
            "crs": boundary_gdf.crs.to_string(),
            "transform": transform,
            "nodata": nodata_val
        }

        with memfile.open(**meta) as dataset:
            dataset.write(Z.astype("float32"), 1)
            out_image, out_transform = mask(
                dataset,
                boundary_gdf.geometry,
                crop=True,
                nodata=nodata_val
            )

    Z_masked = out_image[0]
    Z_masked[Z_masked == nodata_val] = np.nan

    return Z_masked, out_transform

def save_raster(Z, transform, out_path, boundary_gdf):

    Z_out = Z.copy()
    Z_out[np.isnan(Z_out)] = nodata_val

    out_meta = {
        "driver": "GTiff",
        "height": Z_out.shape[0],
        "width": Z_out.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": boundary_gdf.crs.to_string(),
        "transform": transform,
        "nodata": nodata_val
    }

    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(Z_out.astype("float32"), 1)

# ==================
# COMPUTE GLOBAL MAX

def compute_topic_global_max(points, topics_by_category, topic_col):

    global_max = {}

    for cat_name, topics_dict in topics_by_category.items():

        cat_values = categories[cat_name]
        subset_cat = points[points["Kategori"].isin(cat_values)]

        max_val = 0

        for topic_ids in topics_dict.values():

            subset = subset_cat[subset_cat[topic_col].isin(topic_ids)]

            if subset.empty:
                continue

            Z_raw, transform, _ = create_kde_raster(
                subset, boundary, radius_m, pixel_size
            )

            Z_masked, _ = mask_array_to_boundary(
                Z_raw, transform, boundary
            )

            max_val = max(max_val, np.nanmax(Z_masked))

        global_max[cat_name] = max_val
        print(f"{cat_name} topic global max: {max_val:.3f}")

    return global_max

# =======================
# RUN SUBSET KDE (TOPICS)

def run_topic_kde(points, topics_by_category, topic_col="topic"):

    summary = []

    print("\nRunning TOPIC KDEs\n")

    for cat_name, topics_dict in topics_by_category.items():

        cat_values = categories[cat_name]
        subset_cat = points[points["Kategori"].isin(cat_values)]

        for short_name, topic_ids in topics_dict.items():

            subset = subset_cat[
                subset_cat[topic_col].isin(topic_ids)
            ]

            if subset.empty:
                continue

            Z_raw, transform, _ = create_kde_raster(
                subset, boundary, radius_m, pixel_size
            )

            Z_masked, transform_masked = mask_array_to_boundary(
                Z_raw, transform, boundary
            )

            # ---- SAVE RAW ----
            save_raster(
                Z_masked,
                transform_masked,
                os.path.join(
                    output_folder,
                    f"KDE_TOPIC_{short_name}_{cat_name}_RAW.tif"
                ),
                boundary
            )

            # ---- SAVE RELATIVE ----
            Z_norm = Z_masked / GLOBAL_KDE_MAX[cat_name]

            save_raster(
                Z_norm,
                transform_masked,
                os.path.join(
                    output_folder,
                    f"KDE_TOPIC_{short_name}_{cat_name}_RELATIVE.tif"
                ),
                boundary
            )

            print(
                f"{cat_name} | {short_name} "
                f"max raw: {np.nanmax(Z_masked):.3f} | "
                f"max relative: {np.nanmax(Z_norm):.3f}"
            )

            summary.append({
                "Category": cat_name,
                "Topic": short_name,
                "Points": len(subset)
            })

    return pd.DataFrame(summary)

# ==========
# RUN SCRIPT

# compute global max across all topics per category
GLOBAL_KDE_MAX = compute_topic_global_max(
    points,
    topics_to_map,
    topic_col="topic"
)

# run topic KDE
topic_summary = run_topic_kde(
    points,
    topics_to_map,
    topic_col="topic"
)

print("\nTopic KDE point counts:")
print(topic_summary.to_string(index=False))

# === OUTPUT ===
#
# Praise topic global max: 0.000
# Ideas topic global max: 0.000
# Error_Complaints topic global max: 0.000
#
# Running TOPIC KDEs
#
# Praise | bastu_bastun_sauna max raw: 0.000 | max relative: 1.000
# Praise | blommor_tulpaner_påskliljor max raw: 0.000 | max relative: 0.406
# Praise | cykelbanan_cykelbana_asfalteringen max raw: 0.000 | max relative: 0.268
# Praise | snöröjningen_beröm_tack max raw: 0.000 | max relative: 0.403
# Ideas | cyklisterna_cykelbanan_cykelbana max raw: 0.000 | max relative: 1.000
# Ideas | parkeringsplatser_boendeparkering_parkerar max raw: 0.000 | max relative: 0.862
# Ideas | köer_lindhagensgatan_trafiken max raw: 0.000 | max relative: 0.790
# Error_Complaints | klotter_klotters_hammarbyklotter max raw: 0.000 | max relative: 1.000
# Error_Complaints | översvämning_vattenansamling_vattensamling max raw: 0.000 | max relative: 0.857
#
# Topic KDE point counts:
#         Category                                      Topic  Points
#           Praise                         bastu_bastun_sauna      12
#           Praise                blommor_tulpaner_påskliljor      26
#           Praise         cykelbanan_cykelbana_asfalteringen      13
#           Praise                    snöröjningen_beröm_tack      26
#           Praise                  lekgatan, lekgata, barnen      11
#            Ideas           cyklisterna_cykelbanan_cykelbana      98
#            Ideas parkeringsplatser_boendeparkering_parkerar      27
#            Ideas              köer_lindhagensgatan_trafiken      29
# Error_Complaints           klotter_klotters_hammarbyklotter    1551
# Error_Complaints översvämning_vattenansamling_vattensamling    1933
#
# Process finished with exit code 0