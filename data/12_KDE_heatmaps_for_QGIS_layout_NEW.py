
import os
import numpy as np
import geopandas as gpd
from sklearn.neighbors import KernelDensity
from scipy.ndimage import gaussian_filter
import rasterio
from rasterio.transform import from_origin
from rasterio.mask import mask
import pandas as pd

# TO DO
# ...

points_path = r"C:/Users/lisajos/PycharmProjects/park_proj/data/tycktill_output/BERTopic_filtered/tycktill_filtered.gpkg"
points_layername = "pts_in_parks_with_topics"

boundary_path = r"C:/Users/lisajos/QGIS_Projects/Output/Stadsdelsomraden_Stadskartan.gpkg"
boundary_layername = "stadsdelsnmnder"

output_folder = r"C:\Users\lisajos\PycharmProjects\park_proj\data\qgis_maps\TIFFs"
os.makedirs(output_folder, exist_ok=True)

# modes
TEST_MODE = True            # use TRUE to run a subset and not the full script with totals and all combinations
COMPARABLE_TOTALS = False    # use TRUE to make total rasters that are comparable to all other raster within the same category
#SAVE_RAW = False

# KDE parameters
radius_m = 450        # KDE bandwidth in meters  # tidigare 250
pixel_size = 50       # pixel size in meters
gaussian_sigma = 5    # only applied to Praise + Ideas
nodata_val = -9999.0
GLOBAL_KDE_MAX = {}

categories = {
    "Praise": ["Beröm"],
    "Ideas": ["Idé"],
    "Error_Complaints": ["Felanmälan", "Klagomål"]
}

seasons = {
    "Winter": [12, 1, 2],
    "Spring": [3, 4, 5],
    "Summer": [6, 7, 8],
    "Autumn": [9, 10, 11]
}

week_groups = {
    #"Weekday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], # Normaliseringen eller whatever som gör att man kan köra 2 och 5 dagar är fortfarande kvar
    "Weekday": ["Tuesday", "Wednesday", "Thursday"],
    #"Weekend": ["Saturday", "Sunday"]
    "Weekend": ["Friday", "Saturday", "Sunday"]
}

hour_groups = {
    "Night": list(range(0, 5)),        # 00 01 02 03 04 05
    "Morning": list(range(6, 11)),     # 06 07 08 09 10 11
    "Midday": list(range(12, 17)),     # 12 13 14 15 16 17
    "Evening": list(range(18, 23))     # 18 19 20 21 22 23
}

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

########
print("TOTAL Maintenance request points:", len(points[points["Kategori"].isin(["Felanmälan"])]))
print("TOTAL Complaints points:", len(points[points["Kategori"].isin(["Klagomål"])]))

print("TOTAL Praise points:", len(points[points["Kategori"].isin(["Beröm"])]))
print("Weekend Praise points:", len(points[
    (points["Kategori"].isin(["Beröm"])) &
    (points["weekday"].isin(["Friday","Saturday","Sunday"]))
]))
print("Weekday Praise points:", len(points[
    (points["Kategori"].isin(["Beröm"])) &
    (points["weekday"].isin(["Tuesday","Wednesday","Thursday"]))
]))
########


# ======================

# global storage for normalization
GLOBAL_KDE_MAX = {}

# ======================
# KDE + raster functions
# ======================

def create_kde_raster(points_gdf, boundary_gdf, radius_m, pixel_size):
    coords = np.array([(pt.x, pt.y) for pt in points_gdf.geometry])

    if len(coords) == 0:
        return None, None, None

    # define raster extent (aligned to pixel grid)
    minx, miny, maxx, maxy = boundary_gdf.total_bounds
    x_grid = np.arange(minx, maxx + pixel_size, pixel_size)
    y_grid = np.arange(maxy, miny - pixel_size, -pixel_size)
    X, Y = np.meshgrid(x_grid, y_grid)
    grid_coords = np.vstack([X.ravel(), Y.ravel()]).T

    # KDE
    kde = KernelDensity(bandwidth=radius_m, kernel='gaussian')
    kde.fit(coords)

    Z_raw = np.exp(kde.score_samples(grid_coords)).reshape(X.shape)

    # rasterio transform
    transform = from_origin(minx, maxy, pixel_size, pixel_size)

    return Z_raw, transform, Z_raw.shape

# ======================
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

    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(Z.astype("float32"), 1)

    # mask to boundary
    with rasterio.open(out_path) as src:
        out_image, out_transform = mask(src, boundary_gdf.geometry, crop=True, nodata=nodata_val, filled=True)
        out_meta_clipped = src.meta.copy()
        out_meta_clipped.update({"height": out_image.shape[1], "width": out_image.shape[2], "transform": out_transform})

    with rasterio.open(out_path, "w", **out_meta_clipped) as dst:
        dst.write(out_image)

# ======================
def run_total_kde(points, categories, boundary, radius_m, pixel_size):
    """
    Compute KDE for all points in each category (TOTAL) and store global max
    """
    print("\nRunning TOTAL category KDEs\n")
    for cat_name, cat_values in categories.items():
        subset = points[points["Kategori"].isin(cat_values)]
        Z_raw, transform, shape = create_kde_raster(subset, boundary, radius_m, pixel_size)
        if Z_raw is None:
            continue

        # store global max for normalization
        GLOBAL_KDE_MAX[cat_name] = np.nanmax(Z_raw)

        # save total raster
        Z_norm = Z_raw / GLOBAL_KDE_MAX[cat_name]
        save_raster(
            Z_norm, transform, shape,
            os.path.join(output_folder, f"KDE_TOTAL_{cat_name}.tif"),
            boundary,
            nodata_val
        )

# ======================
def run_kde(points, categories, time_groups, time_col, label_name, boundary, radius_m, pixel_size, only_category=None, only_group=None):
    """
    Compute KDEs for subsets (weekdays/weekends, seasons, etc.)
    Normalization is done relative to TOTAL category KDE
    """
    summary = []

    total_jobs = len(categories) * len(time_groups)
    job_counter = 0

    print(f"\nStarting KDE run for: {label_name}")
    print(f"Total rasters to process: {total_jobs}\n")

    for cat_name, cat_values in categories.items():
        if only_category and cat_name != only_category:
            continue

        subset_cat = points[points["Kategori"].isin(cat_values)]

        for group_name, group_values in time_groups.items():
            if only_group and group_name != only_group:
                continue

            job_counter += 1
            print(f"[{job_counter}/{total_jobs}] {label_name}: {group_name} | Category: {cat_name}")

            subset = subset_cat[subset_cat[time_col].isin(group_values)]

            if len(subset) == 0:
                continue

            Z_subset, transform, shape = create_kde_raster(subset, boundary, radius_m, pixel_size)
            if Z_subset is None:
                continue

            # normalize relative to total KDE
            Z_norm = Z_subset / GLOBAL_KDE_MAX[cat_name]

            # optional Gaussian smoothing (apply to all categories, not just Praise/Ideas)
            if gaussian_sigma is not None:
                Z_norm = gaussian_filter(Z_norm, sigma=gaussian_sigma)

            save_raster(
                Z_norm, transform, shape,
                os.path.join(output_folder, f"KDE_{cat_name}_{group_name}.tif"),
                boundary,
                nodata_val
            )

            summary.append({
                "Category": cat_name,
                label_name: group_name,
                "Points": len(subset)
            })

    return pd.DataFrame(summary)

# ======================
# RUN SCRIPT
# ======================

if TEST_MODE:
    test_category = "Error_Complaints"
    # TOTAL
    run_total_kde(points, {test_category: categories[test_category]}, boundary, radius_m, pixel_size)
    # SUBSET (Weekend)
    subset_summary = run_kde(
        points,
        {test_category: categories[test_category]},
        week_groups,
        "weekday",
        "WeekType",
        boundary,
        radius_m,
        pixel_size,
        only_category=test_category,
        only_group="Weekend"
    )
else:
    # TOTALS
    run_total_kde(points, categories, boundary, radius_m, pixel_size)

    # SEASONS
    season_summary = run_kde(points, categories, seasons, "month", "Season", boundary, radius_m, pixel_size)

    # WEEKDAY/WEEKEND
    weekday_summary = run_kde(points, categories, week_groups, "weekday", "WeekType", boundary, radius_m, pixel_size)

    # TIME OF DAY
    hour_summary = run_kde(points, categories, hour_groups, "hour", "TimeOfDay", boundary, radius_m, pixel_size)

    print("\nSeasonal KDE point counts:")
    print(season_summary.to_string(index=False))
    print("\nWeekday / Weekend KDE point counts:")
    print(weekday_summary.to_string(index=False))
    print("\nTime-of-day KDE point counts:")
    print(hour_summary.to_string(index=False))

# Seasonal KDE point counts:
#         Category Season  Points
#           Praise Winter      95
#           Praise Spring      83
#           Praise Summer      85
#           Praise Autumn      38
#            Ideas Winter     152
#            Ideas Spring     223
#            Ideas Summer     235
#            Ideas Autumn     219
# Error_Complaints Winter   12153
# Error_Complaints Spring   20412
# Error_Complaints Summer   25187
# Error_Complaints Autumn   19572
#
# Weekday / Weekend KDE point counts:
#         Category WeekType  Points
#           Praise  Weekday     153
#           Praise  Weekend     110
#            Ideas  Weekday     368
#            Ideas  Weekend     338
# Error_Complaints  Weekday   34637
# Error_Complaints  Weekend   29871
#
# Time-of-day KDE point counts:
#         Category TimeOfDay  Points
#           Praise     Night       5
#           Praise   Morning      80
#           Praise    Midday     108
#           Praise   Evening      67
#            Ideas     Night       9
#            Ideas   Morning     225
#            Ideas    Midday     269
#            Ideas   Evening     206
# Error_Complaints     Night     584
# Error_Complaints   Morning   22673
# Error_Complaints    Midday   29330
# Error_Complaints   Evening   13004
#
# Process finished with exit code 0
