
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

output_folder = r"C:\Users\lisajos\PycharmProjects\park_proj\data\qgis_maps\TIFFs"
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

# =========
# constants

# KDE parameters
radius_m = 250        # KDE bandwidth in meters
pixel_size = 50       # pixel size in meters
gaussian_sigma = 5    # only applied to Praise + Ideas
nodata_val = -9999.0
GLOBAL_KDE_MAX = {}

SAVE_RAW = False

topics_to_map = {    # *** använd meta-topics istället? ***
    "Praise": {
        "bastu_bastun_sauna": [600],
        "blommor_tulpaner_påskliljor": [457],
        "cykelbanan_cykelbana_asfalteringen": [485],
        "snöröjningen_beröm_tack": [136],
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

# ====================================
# helper function to create KDE raster

def create_kde_raster(points_gdf, boundary_gdf, radius_m, pixel_size, gaussian_sigma=None):

    coords = np.array([(pt.x, pt.y) for pt in points_gdf.geometry])

    if len(coords) == 0:
        return None, None, None, None

    # define raster extent (aligned to pixel grid)
    minx, miny, maxx, maxy = boundary_gdf.total_bounds
    x_grid = np.arange(minx, maxx + pixel_size, pixel_size)
    y_grid = np.arange(maxy, miny - pixel_size, -pixel_size)
    X, Y = np.meshgrid(x_grid, y_grid)

    grid_coords = np.vstack([X.ravel(), Y.ravel()]).T

    # KDE
    kde = KernelDensity(bandwidth=radius_m, kernel='gaussian')
    kde.fit(coords)

    # normalise
    kde = KernelDensity(bandwidth=radius_m, kernel="gaussian")
    kde.fit(coords)

    Z_raw = np.exp(kde.score_samples(grid_coords)).reshape(X.shape)

    # extra gaussian smoothing
    Z_gauss = None
    if gaussian_sigma is not None:
        Z_gauss = gaussian_filter(Z_raw, sigma=gaussian_sigma)

    # rasterio transform
    transform = from_origin(minx, maxy, pixel_size, pixel_size)

    return Z_raw, Z_gauss, transform, Z_raw.shape


# =====================================
# helper function to save + mask raster

def save_raster(Z, transform, shape, out_path, boundary_gdf, nodata_val):
    out_meta = {
        "driver": "GTiff",
        "height": shape[0],
        "width": shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": boundary_gdf.crs.to_string(),
        "transform": transform,
        "nodata": nodata_val
    }

    # write full raster
    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(Z.astype("float32"), 1)

    # reopen and mask
    with rasterio.open(out_path) as src:
        out_image, out_transform = mask(
            src,
            boundary_gdf.geometry,
            crop=True,
            nodata=nodata_val,
            filled=True
        )

        out_meta_clipped = src.meta.copy()
        out_meta_clipped.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform
        })

    # overwrite with clipped raster
    with rasterio.open(out_path, "w", **out_meta_clipped) as dst:
        dst.write(out_image)

# ======================
# helper function to run

def run_topic_kde(points, topics_by_category, topic_col="topic", normalize=False):

    global GLOBAL_KDE_MAX
    if not normalize:
        GLOBAL_KDE_MAX = {}

    summary = []

    total_jobs = sum(len(v) for v in topics_by_category.values())
    job_counter = 0

    print(f"\nStarting TOPIC KDE run")
    print(f"Total rasters to process: {total_jobs}\n")

    for cat_name, topics_dict in topics_by_category.items():
        cat_values = categories[cat_name]

        for short_name, topic_ids in topics_dict.items():
            job_counter += 1
            print(
                f"[{job_counter}/{total_jobs}] "
                f"Topic: {cat_name} | Category: {short_name}"
            )

            subset = points[
                points["Kategori"].isin(cat_values) &
                points[topic_col].isin(topic_ids)
            ]

            if subset.empty:
                continue

            Z_raw, Z_gauss, transform, shape = create_kde_raster(
                subset,
                boundary,
                radius_m,
                pixel_size,
                gaussian_sigma=gaussian_sigma if cat_name != "Error_Complaints" else None
            )

            if Z_raw is None:
                continue

            Z_out = Z_gauss if Z_gauss is not None else Z_raw

            # update global max per category
            local_max = np.nanmax(Z_out)

            GLOBAL_KDE_MAX[cat_name] = max(
                GLOBAL_KDE_MAX.get(cat_name, 0),
                local_max
            )

            summary.append({
                "Category": cat_name,
                "Topic": short_name,
                "Points": len(subset)
            })

            if SAVE_RAW and not normalize:
                save_raster(
                    Z_out,
                    transform,
                    shape,
                    os.path.join(
                        output_folder,
                        f"KDE_TOPIC_{short_name}_{cat_name}_RAW.tif"
                    ),
                    boundary,
                    nodata_val
                )

            if normalize:
                Z_norm = Z_out / GLOBAL_KDE_MAX[cat_name]

                save_raster(
                    Z_norm,
                    transform,
                    shape,
                    os.path.join(
                        output_folder,
                        f"KDE_TOPIC_{short_name}_{cat_name}_NORM.tif"
                    ),
                    boundary,
                    nodata_val
                )

    return pd.DataFrame(summary)

topic_summary = run_topic_kde(
    points,
    topics_to_map,
    topic_col="topic",   # <-- adjust to your column name
    normalize=False
)

print("Topic KDE max per category:")
print(GLOBAL_KDE_MAX)

# Normalized run
run_topic_kde(
    points,
    topics_to_map,
    topic_col="topic",
    normalize=True
)

print("\nTopic KDE point counts:")
print(topic_summary.to_string(index=False))
