
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
COMPARABLE_TOTALS = True    # use TRUE to make total rasters that are comparable to all other raster within the same category
SAVE_RAW = False

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

# ======================
# KDE + raster functions

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
    # Z_gauss = None
    # if gaussian_sigma is not None:
    #     Z_gauss = gaussian_filter(Z_raw, sigma=gaussian_sigma)

    # rasterio transform
    transform = from_origin(minx, maxy, pixel_size, pixel_size)

    #return Z_raw, Z_gauss, transform, Z_raw.shape
    return Z_raw, transform, Z_raw.shape

##########
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
##########

def run_total_kde(points, only_category=None):

    print("\nRunning TOTAL category KDEs\n")

    for cat_name, cat_values in categories.items():
        if only_category is not None and cat_name != only_category:
            continue

        print(f"Processing TOTAL KDE for {cat_name}")

        subset = points[points["Kategori"].isin(cat_values)]
        Z_raw, transform, shape = create_kde_raster(subset, boundary, radius_m, pixel_size)

        if Z_raw is None:
            continue

            # Update global max for normalization
        GLOBAL_KDE_MAX[cat_name] = np.nanmax(Z_raw)

        # Save total raster if not using COMPARABLE_TOTALS (old behavior)
        if not COMPARABLE_TOTALS:
            Z_norm = Z_raw / GLOBAL_KDE_MAX[cat_name]
            # Apply Gaussian smoothing after normalization if desired
            if gaussian_sigma is not None and cat_name in ["Praise", "Ideas"]:
                Z_norm = gaussian_filter(Z_norm, sigma=gaussian_sigma)

            save_raster(
                Z_norm, transform, shape,
                os.path.join(output_folder, f"KDE_TOTAL_{cat_name}.tif"),
                boundary, nodata_val
            )

        # Z, _, transform, shape = create_kde_raster(
        #     subset,
        #     boundary,
        #     radius_m,
        #     pixel_size,
        #     gaussian_sigma=gaussian_sigma
        # )
        #
        # if Z is None:
        #     continue
        #
        # if COMPARABLE_TOTALS:
        #     # update shared max but do NOT normalize yet
        #     local_max = np.nanmax(Z)
        #
        #     GLOBAL_KDE_MAX[cat_name] = max(GLOBAL_KDE_MAX.get(cat_name, 0), local_max)

            # if cat_name not in GLOBAL_KDE_MAX:
            #     GLOBAL_KDE_MAX[cat_name] = local_max
            # else:
            #     GLOBAL_KDE_MAX[cat_name] = max(GLOBAL_KDE_MAX[cat_name], local_max)

            # temporarily store raw
        #     np.save(os.path.join(output_folder, f"TMP_TOTAL_{cat_name}.npy"), Z)
        #
        # else:
        #     # old behaviour: normalize independently
        #     Z = Z / np.nanmax(Z)
        #
        #     save_raster(
        #         Z,
        #         transform,
        #         shape,
        #         os.path.join(output_folder, f"KDE_TOTAL_{cat_name}.tif"),
        #         boundary,
        #         nodata_val
        #     )

        # local_max = np.nanmax(Z)
        #
        # if cat_name not in GLOBAL_KDE_MAX:
        #     GLOBAL_KDE_MAX[cat_name] = local_max
        # else:
        #     GLOBAL_KDE_MAX[cat_name] = max(GLOBAL_KDE_MAX[cat_name], local_max)
        #
        # # store temporarily for later normalization
        # np.save(os.path.join(output_folder, f"TMP_TOTAL_{cat_name}.npy"), Z)

        # # normalize to 0–1
        # Z = Z / np.nanmax(Z)
        #
        # save_raster(
        #     Z,
        #     transform,
        #     shape,
        #     os.path.join(output_folder, f"KDE_TOTAL_{cat_name}.tif"),
        #     boundary,
        #     nodata_val
        # )

def save_normalized_totals():

    print("\nSaving normalized TOTAL rasters\n")

    for cat_name in categories.keys():

        tmp_path = os.path.join(output_folder, f"TMP_TOTAL_{cat_name}.npy")

        if not os.path.exists(tmp_path):
            continue

        Z = np.load(tmp_path)
        Z_norm = Z / GLOBAL_KDE_MAX[cat_name]

        # recreate transform & shape
        _, _, transform, shape = create_kde_raster(points[points["Kategori"].isin(categories[cat_name])],
                                                   boundary, radius_m, pixel_size, gaussian_sigma=gaussian_sigma)

        save_raster(Z_norm, transform, shape, os.path.join(output_folder, f"KDE_TOTAL_{cat_name}.tif"), boundary,
                    nodata_val)
        os.remove(tmp_path)

        # # recreate transform + shape
        # Z_dummy, _, transform, shape = create_kde_raster(
        #     points[points["Kategori"].isin(categories[cat_name])],
        #     boundary,
        #     radius_m,
        #     pixel_size,
        #     gaussian_sigma=gaussian_sigma
        # )
        #
        # save_raster(
        #     Z_norm,
        #     transform,
        #     shape,
        #     os.path.join(output_folder, f"KDE_TOTAL_{cat_name}_NORM.tif"),
        #     boundary,
        #     nodata_val
        # )
        #
        # os.remove(tmp_path)


# ===========
# time groups

def run_kde(points, time_groups, time_col, label_name, normalize=False, only_category=None, only_group=None):

    summary = []

    global GLOBAL_KDE_MAX
    if not normalize:
        GLOBAL_KDE_MAX = {}

    total_jobs = len(categories) * len(time_groups)
    job_counter = 0

    print(f"\nStarting KDE run for: {label_name}")
    print(f"Total rasters to process: {total_jobs}\n")

    for cat_name, cat_values in categories.items():

        if only_category and cat_name != only_category:
            continue

        for group_name, group_values in time_groups.items():

            if only_group and group_name != only_group:
                continue

            job_counter += 1
            print(
                f"[{job_counter}/{total_jobs}] "
                f"{label_name}: {group_name} | Category: {cat_name}"
            )

            subset = points[
                points["Kategori"].isin(cat_values) &
                points[time_col].isin(group_values)
            ]

            # per-day KDEs
            daily_rasters = []
            days = subset["Inkommet datum"].dt.date.unique()

            for day in days:
                day_subset = subset[subset["Inkommet datum"].dt.date == day]
                Z_day, transform, shape = create_kde_raster(day_subset, boundary, radius_m, pixel_size)
                if Z_day is not None:
                    daily_rasters.append(Z_day)
            if not daily_rasters:
                continue


            # mean KDE
            Z_mean = np.mean(daily_rasters, axis=0)

            # normalize using global max from totals
            if COMPARABLE_TOTALS:
                Z_norm = Z_mean / GLOBAL_KDE_MAX[cat_name]
            else:
                Z_norm = Z_mean / np.nanmax(Z_mean)

            # Gaussian smoothing after normalization
            if gaussian_sigma is not None and cat_name in ["Praise", "Ideas"]:
                Z_norm = gaussian_filter(Z_norm, sigma=gaussian_sigma)

            save_raster(
                Z_norm, transform, shape,
                os.path.join(output_folder, f"KDE_{cat_name}_{group_name}.tif"),
                boundary, nodata_val
            )

            summary.append({
                "Category": cat_name,
                label_name: group_name,
                "Days": len(days),
                "Points": len(subset)
            })




            #     Z_day, _, transform, shape = create_kde_raster(
            #         day_subset,
            #         boundary,
            #         radius_m,
            #         pixel_size,
            #         #category=cat_name,
            #         gaussian_sigma=None,  # smooth AFTER averaging
            #         #normalize=False
            #     )
            #
            #     if Z_day is not None:
            #         daily_rasters.append(Z_day)
            #
            # if not daily_rasters:
            #     continue
            #
            # # mean KDE (equal weight per day)
            # Z_mean = np.mean(daily_rasters, axis=0)
            #
            # # optional gaussian smoothing
            # if gaussian_sigma is not None:
            #     Z_mean = gaussian_filter(Z_mean, sigma=gaussian_sigma)
            #
            # # update global max (PER CATEGORY)
            # local_max = np.nanmax(Z_mean)
            # GLOBAL_KDE_MAX[cat_name] = max(GLOBAL_KDE_MAX.get(cat_name, 0), local_max)
            # # if cat_name not in GLOBAL_KDE_MAX:
            # #     GLOBAL_KDE_MAX[cat_name] = local_max
            # # else:
            # #     GLOBAL_KDE_MAX[cat_name] = max(GLOBAL_KDE_MAX[cat_name], local_max)
            #
            # summary.append({
            #     "Category": cat_name,
            #     label_name: group_name,
            #     "Days": len(days),
            #     "Points": len(subset)
            # })
            #
            # if SAVE_RAW and not normalize:
            #     save_raster(Z_mean, transform, shape,
            #                 os.path.join(output_folder, f"KDE_{cat_name}_{group_name}_RAW_MEAN.tif"), boundary,
            #                 nodata_val)
            #
            # if normalize:
            #     Z_norm = Z_mean / GLOBAL_KDE_MAX[cat_name]
            #     save_raster(Z_norm, transform, shape,
            #                 os.path.join(output_folder, f"KDE_{cat_name}_{group_name}_GAUSS_NORM.tif"), boundary,
            #                 nodata_val)

            # # OPTIONAL: save RAW mean KDE (unnormalized)
            # if SAVE_RAW and not normalize:
            #     save_raster(
            #         Z_mean,
            #         transform,
            #         shape,
            #         os.path.join(
            #             output_folder,
            #             f"KDE_{cat_name}_{group_name}_RAW_MEAN.tif"
            #         ),
            #         boundary,
            #         nodata_val
            #     )
            #
            # if normalize:
            #
            #     Z_norm = Z_mean / GLOBAL_KDE_MAX[cat_name]
            #
            #     save_raster(
            #         Z_norm,
            #         transform,
            #         shape,
            #         os.path.join(
            #             output_folder,
            #             f"KDE_{cat_name}_{group_name}_GAUSS_NORM.tif"
            #         ),
            #         boundary,
            #         nodata_val
            #     )

    return pd.DataFrame(summary)

# def save_raster(Z, transform, shape, out_path, boundary_gdf, nodata_val):
#     out_meta = {
#         "driver": "GTiff",
#         "height": shape[0],
#         "width": shape[1],
#         "count": 1,
#         "dtype": "float32",
#         "crs": boundary_gdf.crs.to_string(),
#         "transform": transform,
#         "nodata": nodata_val
#     }
#
#     # write full raster
#     with rasterio.open(out_path, "w", **out_meta) as dst:
#         dst.write(Z.astype("float32"), 1)
#
#     # reopen and mask
#     with rasterio.open(out_path) as src:
#         out_image, out_transform = mask(
#             src,
#             boundary_gdf.geometry,
#             crop=True,
#             nodata=nodata_val,
#             filled=True
#         )
#
#         out_meta_clipped = src.meta.copy()
#         out_meta_clipped.update({
#             "height": out_image.shape[1],
#             "width": out_image.shape[2],
#             "transform": out_transform
#         })
#
#     # overwrite with clipped raster
#     with rasterio.open(out_path, "w", **out_meta_clipped) as dst:
#         dst.write(out_image)

# reset max storage
#GLOBAL_KDE_MAX = {}

if TEST_MODE:

    test_category = "Praise"

    run_total_kde(points, only_category=test_category)

    run_kde(points,
            week_groups,
            "weekday",
            "WeekType",
            normalize=True,
            only_category=test_category,
            only_group="Weekend")

    if COMPARABLE_TOTALS:
        save_normalized_totals()

else:

    # ===== TOTALS =====
    run_total_kde(points)

    # ===== SEASONS =====
    season_summary = run_kde(points, seasons, "month", "Season")
    print(f"Season KDE max: {GLOBAL_KDE_MAX}")
    run_kde(points, seasons, "month", "Season", normalize=True)

    # ===== WEEKDAY / WEEKEND =====
    weekday_summary = run_kde(points, week_groups, "weekday", "WeekType")
    print(f"WeekType KDE max: {GLOBAL_KDE_MAX}")
    run_kde(points, week_groups, "weekday", "WeekType", normalize=True)

    # ===== TIME OF DAY =====
    hour_summary = run_kde(points, hour_groups, "hour", "TimeOfDay")
    print(f"TimeOfDay KDE max: {GLOBAL_KDE_MAX}")
    run_kde(points, hour_groups, "hour", "TimeOfDay", normalize=True)

    if COMPARABLE_TOTALS:
        save_normalized_totals()

    print("\nSeasonal KDE point counts:")
    print(season_summary.to_string(index=False))

    print("\nWeekday / Weekend KDE point counts:")
    print(weekday_summary.to_string(index=False))

    print("\nTime-of-day KDE point counts:")
    print(hour_summary.to_string(index=False))

    if COMPARABLE_TOTALS:

        for cat_name in categories.keys():

            tmp_path = os.path.join(output_folder, f"TMP_TOTAL_{cat_name}.npy")

            if not os.path.exists(tmp_path):
                continue

            Z = np.load(tmp_path)

            Z_norm = Z / GLOBAL_KDE_MAX[cat_name]

            # recreate transform/shape
            Z_dummy, _, transform, shape = create_kde_raster(
                points[points["Kategori"].isin(categories[cat_name])],
                boundary,
                radius_m,
                pixel_size,
                gaussian_sigma=gaussian_sigma
            )

            save_raster(
                Z_norm,
                transform,
                shape,
                os.path.join(output_folder, f"KDE_TOTAL_{cat_name}.tif"),
                boundary,
                nodata_val
            )

            os.remove(tmp_path)

# === OLD ===

# WITH EQUAL SIZED TIME GROUPS
# Seasonal KDE point counts:
#         Category Season  Days  Points
#           Praise Winter    66      95
#           Praise Spring    70      83
#           Praise Summer    70      85
#           Praise Autumn    34      38
#            Ideas Winter   107     152
#            Ideas Spring   130     223
#            Ideas Summer   117     235
#            Ideas Autumn   132     219
# Error_Complaints Winter   181   12153
# Error_Complaints Spring   184   20412
# Error_Complaints Summer   184   25187
# Error_Complaints Autumn   182   19572
#
# Weekday / Weekend KDE point counts:
#         Category WeekType  Days  Points
#           Praise  Weekday   186     240
#           Praise  Weekend    54      61
#            Ideas  Weekday   350     587
#            Ideas  Weekend   136     242
# Error_Complaints  Weekday   522   57686
# Error_Complaints  Weekend   209   19638
#
# Time-of-day KDE point counts:
#         Category TimeOfDay  Days  Points
#           Praise     Night     5       5
#           Praise   Morning    71      80
#           Praise    Midday   101     108
#           Praise   Evening    61      67
#            Ideas     Night     9       9
#            Ideas   Morning   192     225
#            Ideas    Midday   229     269
#            Ideas   Evening   172     206
# Error_Complaints     Night   371     584
# Error_Complaints   Morning   729   22673
# Error_Complaints    Midday   728   29330
# Error_Complaints   Evening   727   13004
#
# Process finished with exit code 0


# WITH GLOBAL MAX ACROSS ALL COMBINATIONS
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
