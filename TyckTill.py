
import geopandas as gpd
import pandas as pd
from collections import Counter

# =================
# === LOAD DATA ===

tycktill_df = pd.read_excel(r'C:\Users\lisajos\QGIS_Projects\TyckTill\NEW\Rådata\Raw_TyckTill_2023-01-01_2024-12-31.xlsx')

# =========================
# ======= OVERVIEW ========

print("\n--- overview ---")
print(tycktill_df.head())

print("\n--- data types ---")
print(tycktill_df.info())

print("\n--- columns ---")
print(tycktill_df.columns)

print("\n--- nulls in columns ---")
print(tycktill_df.isnull().sum())

print("\n--- number of duplicates ---")
print(tycktill_df.duplicated().sum())

print("\n--- duplicate rows ---")
print(tycktill_df[tycktill_df.duplicated(keep=False) == True])

print("\n--- Frequency and proportion of Kategori ---")
print(tycktill_df['Kategori'].value_counts())
print(tycktill_df['Kategori'].value_counts(normalize=True))

# == Date/Time ==

tycktill_df['Inkommet datum'] = pd.to_datetime(tycktill_df['Inkommet datum'], errors='coerce')

print("\n--- Date range ---")
print(tycktill_df['Inkommet datum'].min(), tycktill_df['Inkommet datum'].max()) # *** OBS! januari-22maj 2023 saknas! ***

print("\n--- Entries per day ---")
print(tycktill_df['Inkommet datum'].dt.date.value_counts().sort_index())

tycktill_df['year'] = tycktill_df['Inkommet datum'].dt.year
tycktill_df['month'] = tycktill_df['Inkommet datum'].dt.month
tycktill_df['weekday'] = tycktill_df['Inkommet datum'].dt.day_name()
tycktill_df['hour'] = tycktill_df['Inkommet datum'].dt.hour

print("\n--- Entries per month ---")
print(tycktill_df['month'].value_counts().sort_index())


# == Fritext ==

print("\n--- Overview of Fritext ---")

tycktill_df['comment_length'] = tycktill_df['Fritext'].astype(str).apply(len)
tycktill_df['word_count'] = tycktill_df['Fritext'].astype(str).apply(lambda x: len(x.split()))

summary = tycktill_df.groupby('Kategori').agg(
    entry_count=('Kategori', 'count'),
    avg_comment_length=('comment_length', 'mean')
).reset_index()

print(summary)

print("\n--- Overview of Fritext (most common words) ---")
all_words = ' '.join(tycktill_df['Fritext'].dropna().astype(str)).lower().split()
word_counts = Counter(all_words)
print(word_counts.most_common(50)) # 'klotter', 'elsparkcykel' och 'voi' fins i top50 (övriga är 'på', 'och', 'är' osv)


# ==========================
# === KERNEL DENSITY MAP ===

import folium
from folium.plugins import HeatMap

kategorier = ['Felanmälan', 'Idé', 'Beröm']

for t in kategorier:
    subset = tycktill_df[
        (tycktill_df['Kategori'] == t) &
        tycktill_df['Koordinater_Y'].between(-90, 90) &
        tycktill_df['Koordinater_x'].between(-180, 180) &
        (tycktill_df['Koordinater_Y'] != 0) &
        (tycktill_df['Koordinater_x'] != 0)
    ].dropna(subset=['Koordinater_Y', 'Koordinater_x'])

    heat_data = subset[['Koordinater_Y', 'Koordinater_x']].values.tolist()

    m = folium.Map(location=[subset['Koordinater_Y'].mean(), subset['Koordinater_x'].mean()], zoom_start=10)

    HeatMap(heat_data, radius=10, blur=5, min_opacity=0.3).add_to(m)

    m.save(f"data/heatmap_type_{t}.html")


# ===========================
# ===== join with parks =====

parks = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

tycktill_pts = gpd.GeoDataFrame(
    tycktill_df, geometry=gpd.points_from_xy(
        tycktill_df['Koordinater_x'],
        tycktill_df['Koordinater_Y']
    ),
    crs=4326)

tycktill_pts.to_file("data/tycktill.gpkg", layer="tycktill_pts", driver="GPKG", mode="w")

tycktill_pts_copy = tycktill_pts.copy()

tycktill_pts_copy = tycktill_pts_copy.to_crs(parks.crs)

parks_x_tycktill = gpd.sjoin(tycktill_pts_copy, parks, how="left", predicate="within")
parks_x_tycktill = parks_x_tycktill.drop(columns='index_right', errors='ignore')

parks_x_tycktill.to_file("data/tycktill.gpkg", layer="parks_x_tycktill", driver="GPKG", mode="w")


# ===========================
# ===== clip with parks =====

tycktill_pts_in_parks = gpd.sjoin(tycktill_pts_copy, parks[['group', 'geometry']], how="inner", predicate="within")
tycktill_pts_in_parks = tycktill_pts_in_parks.drop(columns='index_right', errors='ignore')

tycktill_pts_in_parks.to_file("data/tycktill.gpkg", layer="tycktill_pts_in_parks", driver="GPKG", mode="w")

tycktill_pts_in_parks['comment_length'] = tycktill_pts_in_parks['Fritext'].astype(str).apply(len)
tycktill_pts_in_parks['word_count'] = tycktill_pts_in_parks['Fritext'].astype(str).apply(lambda x: len(x.split()))

summary = tycktill_pts_in_parks.groupby('Kategori').agg(
    entry_count=('Kategori', 'count'),
    avg_comment_length=('comment_length', 'mean')
).reset_index()

print(summary)

print("\n--- Overview of Fritext in parks (most common words) ---")
all_words = ' '.join(tycktill_pts_in_parks['Fritext'].dropna().astype(str)).lower().split()
word_counts = Counter(all_words)
print(word_counts.most_common(50)) # 'klotter', 'skräp' och 'papperskorg' finns i top50 (övriga är 'på', 'och', 'är' osv)

# =====================================
# === update parks w tycktill stats ===

summary = tycktill_pts_in_parks.groupby('group').agg(
    num_points=('geometry', 'count'),
    unique_comments=('Fritext', 'nunique'),
).reset_index()

summary['pts_per_hectare'] = summary['num_points'] / (parks.set_index('group').loc[summary['group'], 'park_area'] / 10000)

parks = parks.merge(summary, on='group', how='left')
parks.to_file("data/tycktill.gpkg", layer="tycktill_stats_per_park", driver="GPKG", mode="w")



# ===========================
# === PREPP FOR SENTIMENT ===

# add a column for cleaned up Fritext (formatting the same for all cells)



