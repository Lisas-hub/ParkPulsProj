
# >>> point density rasters <<<

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

output_folder = os.path.join("data", "tyck_till_output", "per_kategori")

# =======================================
# === make a raster for point density ===

municipality = gpd.read_file(f"{input_directory}\\Output\\Kommun_Stadskartan_SWEREF99TM.gpkg").to_crs("EPSG:3006")

target_crs = 3857 # a projected crs is required, 3857

if municipality.crs.to_epsg() != target_crs:
    municipality = municipality.to_crs(target_crs)

# set up for raster
pixel_size = 10
minx, miny, maxx, maxy = municipality.total_bounds
width = int((maxx - minx) / pixel_size)
height = int((maxy - miny) / pixel_size)
transform = from_origin(minx, maxy, pixel_size, pixel_size)
nodata_value = -9999

# rasterize mask
municipality_mask = rasterize(
    shapes=[(geom, 0) for geom in municipality.geometry],
    out_shape=(height, width),
    transform=transform,
    fill=nodata_value,
    dtype='int16'
)

# load point layers per cateory
#categories = {
#    "Klagomål": gpd.read_file("data/tyck_till_output/per_kategori/tycktill_Klagomål.gpkg"),
#    "Beröm": gpd.read_file("data/tyck_till_output/per_kategori/tycktill_Beröm.gpkg"),
#    "Idé": gpd.read_file("data/tyck_till_output/per_kategori/tycktill_Idé.gpkg"),
#}
categories = {
    name: gdf[~gdf.geometry.is_empty & gdf.geometry.notnull()] # dropping rows without coordinates for now,change back to above when OG dataset has been cleaned of these rows
    for name, gdf in {
        "Klagomål": gpd.read_file("data/tyck_till_output/per_kategori/tycktill_Klagomål.gpkg"),
        "Beröm": gpd.read_file("data/tyck_till_output/per_kategori/tycktill_Beröm.gpkg"),
        "Idé": gpd.read_file("data/tyck_till_output/per_kategori/tycktill_Idé.gpkg"),
    }.items()
}

for key in categories:
    if not categories[key].crs.is_projected:
        categories[key] = categories[key].to_crs(epsg=target_crs)
    elif categories[key].crs.to_epsg() != target_crs:
        categories[key] = categories[key].to_crs(epsg=target_crs)


####################################
for name, gdf in categories.items(): # Checking for empty geometries, aka missing coordinates
    print(f"\n{name}")
    print("  Total features:", len(gdf))
    print("  Empty geometries:", gdf.geometry.is_empty.sum())
    print("  Null geometries:", gdf.geometry.isnull().sum())
    print("  Invalid geometries:", (~gdf.is_valid).sum())
####################################


# create point density rasters
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

density_rasters = {} # store for later use in ratio calculation

for name, gdf in categories.items():
    density_data = rasterize_points(gdf)
    masked_density = np.where(municipality_mask == 0, density_data, nodata_value).astype('int16')

    output_path = os.path.join(output_folder, f"point_density_{name}.tif")
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

    density_rasters[name] = density_data  # store for ratios


# ============================
# === complaint/idea ratio ===

complaints = density_rasters["Klagomål"]
ideas = density_rasters["Idé"]
total = complaints + ideas

# avoid division by 0
with np.errstate(divide='ignore', invalid='ignore'):
    ratio = np.true_divide(complaints, total)
    ratio[total == 0] = nodata_value

masked_ratio = np.where(municipality_mask == 0, ratio, nodata_value)

# save
with rasterio.open(
    f"{output_folder}/complaints_idea_ratio.tif",
    'w',
    driver='GTiff',
    height=height,
    width=width,
    count=1,
    dtype='float32',
    crs=municipality.crs,
    transform=transform,
    nodata=nodata_value
) as dst:
    dst.write(masked_ratio.astype('float32'), 1)




# ====================