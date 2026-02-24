
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio.transform import from_origin
from rasterio.mask import mask
from sklearn.neighbors import KernelDensity

# ======================
# PATHS AND PARAMETERS
# ======================
TYCKTILL_FILTERED_GPKG = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\BERTopic_filtered\tycktill_filtered.gpkg"
points_layername = "pts_in_parks_with_topics"
boundary_path = r"C:/Users/lisajos/QGIS_Projects/Output/Stadsdelsomraden_Stadskartan.gpkg"
boundary_layername = "stadsdelsnmnder"
output_folder = r"C:\Users\lisajos\PycharmProjects\park_proj\data\qgis_maps\TIFFs"
os.makedirs(output_folder, exist_ok=True)

TEST_MODE = False

radius_m = 450
pixel_size = 50
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
    "Weekday": ["Tuesday", "Wednesday", "Thursday"],
    "Weekend": ["Friday", "Saturday", "Sunday"]
}

hour_groups = {
    "Night": list(range(0, 5)),
    "Morning": list(range(6, 11)),
    "Midday": list(range(12, 17)),
    "Evening": list(range(18, 23))
}

# ======================
# LOAD DATA
# ======================
points = gpd.read_file(TYCKTILL_FILTERED_GPKG, layer=points_layername)
boundary = gpd.read_file(boundary_path, layer=boundary_layername)

if points.crs != boundary.crs:
    points = points.to_crs(boundary.crs)

points["Inkommet datum"] = pd.to_datetime(
    points["Inkommet datum"], format="mixed", errors="coerce"
)

# ======================
# KDE FUNCTIONS
# ======================

def create_kde_raster(points_gdf, boundary_gdf, radius_m, pixel_size):
    coords = np.array([(pt.x, pt.y) for pt in points_gdf.geometry])
    if len(coords) == 0:
        return None, None, None
    minx, miny, maxx, maxy = boundary_gdf.total_bounds
    x_grid = np.arange(minx, maxx + pixel_size, pixel_size)
    y_grid = np.arange(maxy, miny - pixel_size, -pixel_size)
    X, Y = np.meshgrid(x_grid, y_grid)
    grid_coords = np.vstack([X.ravel(), Y.ravel()]).T
    kde = KernelDensity(bandwidth=radius_m, kernel='gaussian')
    kde.fit(coords)
    #Z_raw = np.exp(kde.score_samples(grid_coords)).reshape(X.shape)
    Z_raw = np.exp(kde.score_samples(grid_coords)).reshape(X.shape)
    Z_raw = Z_raw * len(coords)  # convert to intensity
    transform = from_origin(minx, maxy, pixel_size, pixel_size)
    return Z_raw, transform, Z_raw.shape

def mask_array_to_boundary(Z, transform, boundary_gdf):
    # Mask in-memory
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
            out_image, out_transform = mask(dataset, boundary_gdf.geometry, crop=True, nodata=nodata_val)
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

# ======================
# COMPUTE GLOBAL MAX
# ======================

def compute_category_global_max(points, cat_values, subsets_list):
    subset_total = points[points["Kategori"].isin(cat_values)]
    Z_total, transform, _ = create_kde_raster(subset_total, boundary, radius_m, pixel_size)
    Z_masked, _ = mask_array_to_boundary(Z_total, transform, boundary)
    max_val = np.nanmax(Z_masked)
    for time_groups, time_col in subsets_list:
        for group_values in time_groups.values():
            subset = subset_total[subset_total[time_col].isin(group_values)]
            if len(subset) == 0:
                continue
            Z_sub, transform, _ = create_kde_raster(subset, boundary, radius_m, pixel_size)
            Z_sub_masked, _ = mask_array_to_boundary(Z_sub, transform, boundary)
            max_val = max(max_val, np.nanmax(Z_sub_masked))
    return max_val

# ======================
# RUN TOTAL KDE
# ======================

def run_total_kde(points, categories, boundary):
    print("\nRunning TOTAL KDEs\n")
    for cat_name, cat_values in categories.items():
        subset_total = points[points["Kategori"].isin(cat_values)]
        Z_total, transform, _ = create_kde_raster(subset_total, boundary, radius_m, pixel_size)
        Z_masked, transform_masked = mask_array_to_boundary(Z_total, transform, boundary)
        # SAVE RAW (intensity)
        save_raster(
            Z_masked,
            transform_masked,
            os.path.join(
                output_folder,
                f"KDE_TOTAL_{cat_name}_RAW.tif"
            ),
            boundary
        )
        # SAVE RELATIVE (0–1 scaled)
        Z_norm = Z_masked / GLOBAL_KDE_MAX[cat_name]
        save_raster(
            Z_norm,
            transform_masked,
            os.path.join(
                output_folder,
                f"KDE_TOTAL_{cat_name}_RELATIVE.tif"
            ),
            boundary)

# ======================
# RUN SUBSET KDE
# ======================

def run_kde(points, categories, time_groups, time_col, label_name, boundary):
    print(f"\nRunning subset KDE: {label_name}\n")
    summary = []
    for cat_name, cat_values in categories.items():
        subset_cat = points[points["Kategori"].isin(cat_values)]
        for group_name, group_values in time_groups.items():
            subset = subset_cat[subset_cat[time_col].isin(group_values)]
            if len(subset) == 0:
                continue
            Z_raw, transform, _ = create_kde_raster(subset, boundary, radius_m, pixel_size)
            Z_masked, transform_masked = mask_array_to_boundary(Z_raw, transform, boundary)
            # SAVE RAW
            save_raster(
                Z_masked,
                transform_masked,
                os.path.join(
                    output_folder,
                    f"KDE_{cat_name}_{group_name}_RAW.tif"
                ),
                boundary
            )
            # SAVE RELATIVE
            Z_norm = Z_masked / GLOBAL_KDE_MAX[cat_name]
            save_raster(
                Z_norm,
                transform_masked,
                os.path.join(
                    output_folder,
                    f"KDE_{cat_name}_{group_name}_RELATIVE.tif"
                ),
                boundary
            )
            summary.append({
                "Category": cat_name,
                label_name: group_name,
                "Points": len(subset)
            })
            print(
                f"{cat_name} | {group_name} "
                f"max raw: {np.nanmax(Z_masked):.3f} | "
                f"max relative: {np.nanmax(Z_norm):.3f}"
            )
    return pd.DataFrame(summary)

# ==========
# RUN SCRIPT

subsets_list = [
    (seasons, "month"),
    (week_groups, "weekday"),
    (hour_groups, "hour")
]

# Compute global max for each category
for cat_name, cat_values in categories.items():
    GLOBAL_KDE_MAX[cat_name] = compute_category_global_max(points, cat_values, subsets_list)
    print(f"{cat_name} global max across TOTAL + subsets: {GLOBAL_KDE_MAX[cat_name]:.3f}")

# Run TOTAL
run_total_kde(points, categories, boundary)

# Run subsets and print summaries
season_summary = run_kde(points, categories, seasons, "month", "Season", boundary)
weekday_summary = run_kde(points, categories, week_groups, "weekday", "WeekType", boundary)
hour_summary = run_kde(points, categories, hour_groups, "hour", "TimeOfDay", boundary)

print("\nSeasonal KDE point counts:")
print(season_summary.to_string(index=False))

print("\nWeekday / Weekend KDE point counts:")
print(weekday_summary.to_string(index=False))

print("\nTime-of-day KDE point counts:")
print(hour_summary.to_string(index=False))