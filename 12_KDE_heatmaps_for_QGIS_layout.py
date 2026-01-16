
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

output_folder = r"C:\Users\lisajos\PycharmProjects\park_proj\data\qgis_maps\TEST2"
os.makedirs(output_folder, exist_ok=True)

# KDE parameters
radius_m = 250       # KDE bandwidth in meters
pixel_size = 50      # pixel size in meters
gaussian_sigma = 5   # only applied to Praise + Ideas
nodata_val = -9999.0

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
    "Weekday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "Weekend": ["Saturday", "Sunday"]
}

hour_groups = {
    "Night": list(range(0, 6)),        # 00–05
    "Morning": list(range(6, 10)),     # 06–09
    "Midday": list(range(10, 16)),     # 10–15
    "Evening": list(range(16, 24))     # 16–23
}

# =========
# load data

points = gpd.read_file(points_path, layer=points_layername)
boundary = gpd.read_file(boundary_path, layer=boundary_layername)

if points.crs != boundary.crs:
    points = points.to_crs(boundary.crs)

# ====================================
# helper function to create KDE raster

def create_kde_raster(points_gdf, boundary_gdf, radius_m, pixel_size, gaussian_sigma=None):

    n_points = len(points_gdf)

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

    #Z_kde = np.exp(kde.score_samples(grid_coords)).reshape(X.shape)
    ###############
    # normalise
    # KDE (integrates to 1)
    kde = KernelDensity(bandwidth=radius_m, kernel="gaussian")
    kde.fit(coords)

    Z_raw = np.exp(kde.score_samples(grid_coords)).reshape(X.shape)

    # Scale by number of points (absolute density)
    Z_raw = Z_raw * n_points
    ###############

    # extra gaussian smoothing
    Z_gauss = None
    if gaussian_sigma is not None:
        Z_gauss = gaussian_filter(Z_raw, sigma=gaussian_sigma)

    #Z_kde = Z_kde / Z_kde.max()
    #if Z_gauss is not None:
    #    Z_gauss = Z_gauss / Z_gauss.max()

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

def run_kde(points, time_groups, time_col, label_name):
    summary = []

    total_jobs = len(categories) * len(time_groups)
    job_counter = 0

    print(f"\nStarting KDE run for: {label_name}")
    print(f"Total rasters to process: {total_jobs}\n")

    for cat_name, cat_values in categories.items():
        for group_name, group_values in time_groups.items():

            job_counter += 1
            print(
                f"[{job_counter}/{total_jobs}] "
                f"{label_name}: {group_name} | Category: {cat_name}"
            )

            subset = points[
                points["Kategori"].isin(cat_values) &
                points[time_col].isin(group_values)
            ]

            summary.append({
                "Category": cat_name,
                label_name: group_name,
                "Points": len(subset)
            })

            Z_raw, Z_gauss, transform, shape = create_kde_raster(
                subset,
                boundary,
                radius_m,
                pixel_size,
                gaussian_sigma
            )

            if Z_raw is None:
                continue

            # RAW
            save_raster(
                Z_raw,
                transform,
                shape,
                os.path.join(output_folder, f"KDE_{cat_name}_{group_name}_RAW.tif"),
                boundary,
                nodata_val
            )

            # GAUSSIAN
            if Z_gauss is not None:
                save_raster(
                    Z_gauss,
                    transform,
                    shape,
                    os.path.join(output_folder, f"KDE_{cat_name}_{group_name}_GAUSS.tif"),
                    boundary,
                    nodata_val
                )

    return pd.DataFrame(summary)


# ===================================
# loop through categories and seasons

# for cat_name, cat_values in categories.items():
#     for season_name, month_values in seasons.items():
#
#         # filter points
#         subset = points[
#             points["Kategori"].isin(cat_values) &
#             points["month"].isin(month_values)
#         ]
#
#         point_count = len(subset)
#         kde_summary.append({
#             "Category": cat_name,
#             "Season": season_name,
#             "Points": point_count
#         })
#
#         Z_raw, Z_smooth, transform, shape = create_kde_raster(
#             subset,
#             boundary,
#             radius_m,
#             pixel_size,
#             gaussian_sigma=gaussian_sigma
#         )
#
#         if Z_raw is None:
#             print(f"No points for {cat_name} – {season_name}, skipping.")
#             continue
#
#         # RAW KDE
#         raw_path = os.path.join(
#             output_folder,
#             f"KDE_{cat_name}_{season_name}_RAW.tif"
#         )
#         save_raster(Z_raw, transform, shape, raw_path, boundary, nodata_val)
#
#         # GAUSSIAN-SMOOTHED KDE
#         if Z_smooth is not None:
#             gauss_path = os.path.join(
#                 output_folder,
#                 f"KDE_{cat_name}_{season_name}_GAUSS.tif"
#             )
#             save_raster(Z_smooth, transform, shape, gauss_path, boundary, nodata_val)
#
#         print(f"Saved {cat_name} – {season_name}")

#summary_df = pd.DataFrame(kde_summary)

# Seasons
season_summary = run_kde(points, seasons, "month", "Season")

# Weekday / Weekend
weekday_summary = run_kde(points, week_groups, "weekday", "WeekType")

# Time of day
hour_summary = run_kde(points, hour_groups, "hour", "TimeOfDay")


# summary_df.to_csv(os.path.join(output_folder, "kde_season_counts.csv"), index=False)
# weekday_summary.to_csv(os.path.join(output_folder, "kde_weekday_counts.csv"), index=False)
# hour_summary.to_csv(os.path.join(output_folder, "kde_hour_counts.csv"), index=False)
#
#
#
# print("\nKDE input point counts:")
# print(summary_df.to_string(index=False))

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
#           Praise  Weekday     240
#           Praise  Weekend      61
#            Ideas  Weekday     587
#            Ideas  Weekend     242
# Error_Complaints  Weekday   57686
# Error_Complaints  Weekend   19638
#
# Time-of-day KDE point counts:
#         Category TimeOfDay  Points
#           Praise     Night       8
#           Praise   Morning      63
#           Praise    Midday     117
#           Praise   Evening     113
#            Ideas     Night      11
#            Ideas   Morning     158
#            Ideas    Midday     331
#            Ideas   Evening     329
# Error_Complaints     Night     820
# Error_Complaints   Morning   16071
# Error_Complaints    Midday   36587
# Error_Complaints   Evening   23846
#
# Process finished with exit code 0
