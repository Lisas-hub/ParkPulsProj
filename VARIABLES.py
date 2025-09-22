
import geopandas as gpd
import pandas as pd

input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

# original layer
layer1 = gpd.read_file(f"{input_directory}\\Temp\\Sociotop_2024_edited.gpkg", layer="Sociotop_2024_edit3")
# dissolved layer
layer2 = gpd.read_file(f"{input_directory}\\Temp\\Sociotop_2024_edited.gpkg", layer="Sociotop_2024_edit3_lagad_geometri_dissolve_vclean_dissolve_join")
# Layer prep
layer2 = layer2.reset_index(drop=True)
layer2 = layer2.drop(columns=['fid'], errors='ignore')

# ====== Joining info from Sociotop_2024_edit3 to dissolved version of Sociotop ======

def add_variable_to_layer2(layer1, layer2, column_name, condition_func):

    # Create a column for the variable
    # First default all rows to No
    layer1['column_name'] = 'No'
    # Second update to Yes where TYPE_2 is a certain category
    layer1.loc[condition_func(layer1), column_name] = 'Yes'

    # Spatial join (only for relevant columns)
    joined = gpd.sjoin(
        layer1[['geometry', column_name]],
        layer2[['geometry']],
        how='inner',
        predicate='intersects'
    )

    # Convert Yes/No to numeric and summarize max value per geometry
    joined[column_name + '_numeric'] = joined[column_name].map({'No': 0, 'Yes': 1}).fillna(0)
    summary = joined.groupby('index_right')[column_name + '_numeric'].max().map({0: 'No', 1: 'Yes'})

    # Add result to layer2 (no geometry or other data copied)
    layer2[column_name] = layer2.index.map(summary)

    return layer2

# ====== variable_gardens ======
layer2 = add_variable_to_layer2(
    layer1,
    layer2,
    column_name='variable_gardens',
    condition_func=lambda df: df['TYPE_2'].str.lower() == 'odling'
)

# ===== variable_sports =====
layer2 = add_variable_to_layer2(
    layer1,
    layer2,
    column_name='variable_sports',
    condition_func=lambda df: df['TYPE_2'].str.lower() == 'sport'
)

# ====== variable_schools ======
layer2 = add_variable_to_layer2(
    layer1,
    layer2,
    column_name='variable_schools',
    condition_func=lambda df: df['TYPE_2'].str.lower() == 'skola/fritid'
)

# ====== variable_religious ======
layer2 = add_variable_to_layer2(
    layer1,
    layer2,
    column_name='variable_religious',
    condition_func=lambda df: df['TYPE_2'].str.lower() == 'kyrk-relaterat'
)

# ====== variable_play_areas ======
layer2 = add_variable_to_layer2(
    layer1,
    layer2,
    column_name='variable_play_areas',
    condition_func=lambda df: df['TYPE_2'].str.lower() == 'lek'
)

# ====== variable_swim_areas ======
layer2 = add_variable_to_layer2(
    layer1,
    layer2,
    column_name='variable_swim_areas',
    condition_func=lambda df: df['TYPE_2'].isna() # geopandas isna refers to null values
)

# Drop some unnecessary columns
layer2 = layer2.drop(columns=['AREA', 'Inventering_2', 'change_made'], errors='ignore')

# =======================

# Save result
layer2.reset_index(drop=True).to_file("data/VARIABLES.gpkg", layer="all_variables", driver="GPKG", mode="w") # mode="w" (write) replaces the layer in the GeoPackage cleanly, better to use than OVERWRITE='YES'

