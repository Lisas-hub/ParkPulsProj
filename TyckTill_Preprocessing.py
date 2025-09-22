
import pandas as pd
import numpy as np
import geopandas as gpd
from collections import Counter

input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

tycktill_df = pd.read_excel(f"{input_directory}\\TyckTill\\NEW\\TyckTill_2023-06-01_2025-06-30.xlsx")

# ============================================
# === PRE PROCESSING OF ADDITIONAL COLUMNS ===

# =========
# Kategori

# nothing to fix

# =====================================
# date and time column (Inkommet datum)

# convert to appropriate datetime format
tycktill_df["Inkommet datum"] = pd.to_datetime(tycktill_df["Inkommet datum"], errors="coerce")

# drop rows from 1-30 june 2025 (to get just 2 years: 1 june 2023 to 31 may 2025)
start_date = '2023-06-01'
end_date = '2025-06-01' # if i set 2025-05-31 i only get up until 2025-05-30 23:43:07.590000
mask = (tycktill_df['Inkommet datum'] > start_date) & (tycktill_df['Inkommet datum'] <= end_date)

tycktill_df = tycktill_df.loc[mask]

print(tycktill_df['Inkommet datum'].min(), tycktill_df['Inkommet datum'].max())

# extract date (or time) only
tycktill_df["year"] = tycktill_df["Inkommet datum"].dt.year
tycktill_df["month"] = tycktill_df["Inkommet datum"].dt.month
tycktill_df["day"] = tycktill_df["Inkommet datum"].dt.day
tycktill_df["weekday"] = tycktill_df["Inkommet datum"].dt.day_name()
tycktill_df["hour"] = tycktill_df["Inkommet datum"].dt.hour

# group into period 1 and 2
tycktill_df["custom_year"] = tycktill_df["Inkommet datum"].apply(
    lambda x: x.year if x.month >= 6 else x.year - 1
) # 6 refers to the month of june and 1 year from that

tycktill_df["year_label"] = "June " + tycktill_df["custom_year"].astype(str) + "–May " + (tycktill_df["custom_year"] + 1).astype(str)

# ===========
# coordinates

# handle 0 and null
tycktill_df["Koordinater_x"] = tycktill_df["Koordinater_x"].replace(0, np.nan)
tycktill_df["Koordinater_Y"] = tycktill_df["Koordinater_Y"].replace(0, np.nan)

# =================================
# === PRE PROCESSING OF FRITEXT ===

# FILTERING (removing rows that don't need to be included)

# keep rows that have something in them + remove empty space in the beginning or end of cells and remove any rows that don't have anything left after this
tycktill_df = tycktill_df[tycktill_df["Fritext"].notna() & tycktill_df["Fritext"].str.strip().ne("")]

# remove rows with numbers or symbols (incl emojis) and no text, in other words remove all rows without at least one letter
import re
tycktill_df = tycktill_df[tycktill_df["Fritext"].apply(lambda x: re.search(r"[a-zA-ZåäöÅÄÖ]", str(x)) is not None)]

# make all text lowercase
tycktill_df["clean_Fritext"] = tycktill_df["Fritext"].str.lower()

# clean up text that includes certain symbols or emojis by removing them but keeping the text
tycktill_df["clean_Fritext"] = tycktill_df["clean_Fritext"].str.replace(r"[^a-zA-ZåäöÅÄÖ0-9\s]", "", regex=True)

tycktill_df.to_excel("data/cleaned_dataset.xlsx")


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

summary['park_area'] = summary['group'].map(parks.set_index('group')['park_area'])
summary['tycktill_pts_per_hectare'] = summary['num_points'] / (summary['park_area'] / 10000)
parks = parks.merge(summary, on='group', how='left')

tycktill_pts_in_parks['Kategori'] = tycktill_pts_in_parks['Kategori'].fillna('Okänd')
kategori_counts = tycktill_pts_in_parks.groupby(['group', 'Kategori']).size().unstack(fill_value=0).reset_index()
parks = parks.merge(kategori_counts, on='group', how='left')

parks.to_file("data/tycktill.gpkg", layer="tycktill_stats_per_park", driver="GPKG", mode="w")

