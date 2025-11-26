
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point
import matplotlib.pyplot as plt
from sklearn.neighbors import KernelDensity
from scipy.ndimage import gaussian_filter
from rasterio.features import rasterize
import pandas as pd

path = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\sentiments"

municipality_path = r"C:\Users\lisajos\QGIS_Projects\output\Kommun_Stadskartan_SWEREF99TM.gpkg"
praise_path       = f"{path}/tycktill_Beröm.gpkg"
idea_path         = f"{path}/tycktill_Idé.gpkg"
error_path         = f"{path}/tycktill_Felanmälan.gpkg"
complaint_path         = f"{path}/tycktill_Klagomål.gpkg"

target_crs = 3857

DeSO = gpd.read_file(r"C:\Users\lisajos\QGIS_Projects\Input\SCB\DeSO_2025.gpkg").to_crs(f"EPSG:{target_crs}")
population_table = pd.read_excel(r"C:\Users\lisajos\QGIS_Projects\Input\SCB\SCB_population_by_gender_and_DESO_for_2024.xlsx")

# ================
# load and combine

municipality = gpd.read_file(municipality_path).to_crs(target_crs)

praise = gpd.read_file(praise_path).to_crs(target_crs)
ideas  = gpd.read_file(idea_path).to_crs(target_crs)
praise_idea_points = gpd.GeoDataFrame(pd.concat([praise, ideas], ignore_index=True), crs=target_crs)

error = gpd.read_file(error_path).to_crs(target_crs)
complaint  = gpd.read_file(complaint_path).to_crs(target_crs)
error_complaint_points = gpd.GeoDataFrame(pd.concat([error, complaint], ignore_index=True), crs=target_crs)

if municipality.crs.to_epsg() != target_crs:
    municipality = municipality.to_crs(target_crs)

# ==================
# create raster grid

pixel_size = 50  # finer grid = better KDE
minx, miny, maxx, maxy = municipality.total_bounds
width  = int((maxx - minx) / pixel_size)
height = int((maxy - miny) / pixel_size)
transform = from_origin(minx, maxy, pixel_size, pixel_size)
nodata_value = -9999

# =============================================
# rasterize municipality polygon to create mask

municipality_mask = rasterize(
    [(geom, 1) for geom in municipality.geometry],
    out_shape=(height, width),
    transform=transform,
    fill=nodata_value,
    dtype="int16"
)

municipality_mask_clean = np.where(municipality_mask > 0, 1, 0)

sigma = 2

# =========================
# rasterize DeSO population

# merge latest population table with latest DeSO polygons (from SCB not SLU.GET)
DeSO_pop = DeSO.merge(population_table, on="desokod", how="left")

# rasterize
population_raster = rasterize(
    [(geom, pop) for geom, pop in zip(DeSO_pop.geometry, DeSO_pop.totalt)],
    out_shape=(height, width),
    transform=transform,
    fill=0,
    dtype="float32"
)

population_raster_masked = np.where(municipality_mask_clean == 1, population_raster, 0)

# save
pop_output_path = r"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\plots\DeSO_2024_tot_population.tif"
with rasterio.open(
    pop_output_path,
    "w",
    driver="GTiff",
    height=height,
    width=width,
    count=1,
    dtype=population_raster_masked.dtype,
    crs=f"EPSG:{target_crs}",
    transform=transform,
    compress="lzw"
) as dst:
    dst.write(population_raster_masked, 1)

# ===========================================================
# get kde and kde x pop for praise+ideas and error+complaints

def rasterize_points(points_gdf, height, width, transform):
    """rasterize point layer to raw counts per pixel."""
    return rasterize(
        [(geom, 1) for geom in points_gdf.geometry],
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype="float32",
        merge_alg=rasterio.enums.MergeAlg.add
    )

def kde_smooth(raster, sigma):
    """apply Gaussian smoothing."""
    return gaussian_filter(raster, sigma=sigma, mode='constant', cval=0)

def mask_to_municipality(raster, municipality_mask_clean, nodata=-9999):
    """apply municipal mask, set nodata outside."""
    out = raster.copy()
    out[municipality_mask_clean == 0] = nodata
    out[municipality_mask_clean == 1] = np.where(out[municipality_mask_clean == 1] > 0,
                                                 out[municipality_mask_clean == 1], 0)
    return out

def save_raster(path, array, height, width, transform, crs, nodata=-9999):
    """write single-band GeoTIFF."""
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=array.dtype,
        transform=transform,
        crs=crs,
        nodata=nodata,
        compress="lzw"
    ) as dst:
        dst.write(array, 1)

def per_1000_raster(kde_raster, population_raster_masked, nodata=-9999):
    """calculate KDE per 1000 population."""
    safe_pop = np.where(population_raster_masked > 0, population_raster_masked, np.nan)
    ratio = (kde_raster / safe_pop) * 1000
    return np.where(np.isnan(ratio), nodata, ratio).astype("float32")

def process_topic(points_gdf, out_prefix):

    # rasterize points
    raw = rasterize_points(points_gdf, height, width, transform)

    # KDE smoothing
    kde = kde_smooth(raw, sigma=sigma)

    # mask to municipality
    kde_masked = mask_to_municipality(kde, municipality_mask_clean)

    # save KDE
    kde_path = rf"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\plots\kde_{out_prefix}.tif"
    save_raster(kde_path, kde_masked.astype("float32"), height, width, transform, f"EPSG:{target_crs}")

    # ratio per 1000 residents
    ratio = per_1000_raster(kde_masked, population_raster_masked)

    # save ratio
    ratio_path = rf"C:\Users\lisajos\PycharmProjects\park_proj\data\tycktill_output\plots\{out_prefix}_per_1000_residents.tif"
    save_raster(ratio_path, ratio, height, width, transform, f"EPSG:{target_crs}")

    print(f"✔ Finished {out_prefix}")

process_topic(praise_idea_points, "praise_ideas_comments")
process_topic(error_complaint_points, "error_complaints_comments")



