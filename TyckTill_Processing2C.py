
import geopandas as gpd
import numpy as np
import os
import rasterio
from rasterio.transform import from_origin
from rasterio.features import rasterize
from rasterio.enums import MergeAlg


input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

# =====================================
# set up for saving in the right folder

kategori_input = input("☆☆☆ Enter the Kategori used in the first script (e.g. Felanmälan): ")

if not kategori_input:
    print("❌ enter a valid kategori ❌")
    exit()

output_folder = os.path.join("data", "tyck_till_output", "per_kategori")

# =======================================
# === make a raster for point density ===

points = gpd.read_file(f"{output_folder}\\tycktill_{kategori_input}.gpkg")
municipality = gpd.read_file(f"{input_directory}\\Output\\Kommun_Stadskartan_SWEREF99TM.gpkg").to_crs("EPSG:3006")
# CRS: EPSG:4326  pts
# CRS: EPSG:3006  municipality

if not points.crs.is_projected:
    points = points.to_crs(epsg=3857) # a projected crs is required, 3857

if municipality.crs != points.crs:
    municipality = municipality.to_crs(points.crs)

# set up for raster
pixel_size = 10
minx, miny, maxx, maxy = municipality.total_bounds
width = int((maxx - minx) / pixel_size)
height = int((maxy - miny) / pixel_size)
transform = from_origin(minx, maxy, pixel_size, pixel_size)
nodata_value = -9999

# rasterize mask
shapes = [(geom, 0) for geom in municipality.geometry]

municipality_mask = rasterize(
    shapes=shapes,
    out_shape=(height, width),
    transform=transform,
    fill=nodata_value,          # value outside polygon
    dtype='int16'      # must allow negative values
)

# create another raster with point density
point_shapes = ((geom, 1) for geom in points.geometry)

density_data = rasterize(
    shapes=point_shapes,
    out_shape=(height, width),
    transform=transform,
    fill=0,
    dtype='uint16',
    merge_alg=MergeAlg.add
)

masked_density = np.where(municipality_mask == 0, density_data, nodata_value).astype('int16')

# save
output_path = f"{output_folder}/point_density_{kategori_input}.tif"
with rasterio.open(
    output_path,
    'w',
    driver='GTiff',
    height=height,
    width=width,
    count=1,
    dtype='int16',
    crs=municipality.crs,
    transform=transform,
    nodata=nodata_value
) as dst:
    dst.write(masked_density, 1)


# ============================
# === complaint/idea ratio ===   *** testa lägg in ideer och klagomål, de finns redan körda i A och B ***

ideas =         # load Idé points
complaints =    # load Klagomål points

def rasterize_points(gdf):
    shapes = ((geom, 1) for geom in gdf.geometry)
    return rasterize(
        shapes=shapes,
        out_shape=(height, width),
        transform=transform,
        fill=0,
        dtype='uint16',
        merge_alg=MergeAlg.add
    )

complaint_counts = rasterize_points(complaints)
idea_counts = rasterize_points(ideas)

# compute ratio
total = complaint_counts + idea_counts
# avoid division by 0
with np.errstate(divide='ignore', invalid='ignore'):
    complaint_ratio = np.true_divide(complaint_counts, total)
    complaint_ratio[total == 0] = -9999  # NoData where no points

masked_ratio = np.where(municipality_mask == 0, complaint_ratio, -9999)

# save
with rasterio.open(
    "complaint_ratio.tif",
    'w',
    driver='GTiff',
    height=height,
    width=width,
    count=1,
    dtype='float32',
    crs=municipality.crs,
    transform=transform,
    nodata=-9999
) as dst:
    dst.write(masked_ratio.astype('float32'), 1)




# ====================