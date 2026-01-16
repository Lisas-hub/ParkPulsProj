
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
gaussian_sigma = 5  # only applied to Praise + Ideas

# categories and seasons
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

nodata_val = -9999.0

# =========
# load data

points = gpd.read_file(points_path, layer=points_layername)
boundary = gpd.read_file(boundary_path, layer=boundary_layername)

if points.crs != boundary.crs:
    points = points.to_crs(boundary.crs)

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
    Z_kde = np.exp(kde.score_samples(grid_coords)).reshape(X.shape)

    # extra gaussian smoothing
    Z_gauss = None
    if gaussian_sigma is not None:
        Z_gauss = gaussian_filter(Z_kde, sigma=gaussian_sigma)

    Z_kde = Z_kde / Z_kde.max()
    if Z_gauss is not None:
        Z_gauss = Z_gauss / Z_gauss.max()

    # rasterio transform
    transform = from_origin(minx, maxy, pixel_size, pixel_size)

    return Z_kde, Z_gauss, transform, Z_kde.shape

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

kde_summary = []

# ===================================
# loop through categories and seasons

for cat_name, cat_values in categories.items():
    for season_name, month_values in seasons.items():

        # filter points
        subset = points[
            points["Kategori"].isin(cat_values) &
            points["month"].isin(month_values)
        ]

        point_count = len(subset)
        kde_summary.append({
            "Category": cat_name,
            "Season": season_name,
            "Points": point_count
        })

        Z_raw, Z_smooth, transform, shape = create_kde_raster(
            subset,
            boundary,
            radius_m,
            pixel_size,
            gaussian_sigma=gaussian_sigma
        )

        if Z_raw is None:
            print(f"No points for {cat_name} – {season_name}, skipping.")
            continue

        # RAW KDE
        raw_path = os.path.join(
            output_folder,
            f"KDE_{cat_name}_{season_name}_RAW.tif"
        )
        save_raster(Z_raw, transform, shape, raw_path, boundary, nodata_val)

        # GAUSSIAN-SMOOTHED KDE
        if Z_smooth is not None:
            gauss_path = os.path.join(
                output_folder,
                f"KDE_{cat_name}_{season_name}_GAUSS.tif"
            )
            save_raster(Z_smooth, transform, shape, gauss_path, boundary, nodata_val)

        print(f"Saved {cat_name} – {season_name}")

summary_df = pd.DataFrame(kde_summary)

print("\nKDE input point counts:")
print(summary_df.to_string(index=False))

# KDE input point counts:
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
