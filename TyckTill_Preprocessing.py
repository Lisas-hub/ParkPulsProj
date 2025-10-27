
import pandas as pd
import numpy as np
import geopandas as gpd

input_directory = r"C:\Users\lisajos\QGIS_Projects" # set your directory here

df = pd.read_excel(f"{input_directory}\\TyckTill\\NEW\\Tycktill_2023-06-01_2025-06-30.xlsx")

print("\n--- Before cleaning ---")
print(f"Initially {len(df)} total rows.")

# ==================================
# === PRE PROCESSING OF KATEGORI ===

# nothing to fix

# =============================================
# === date and time column (Inkommet datum) ===

datetime_before = len(df)

# convert to appropriate datetime format
df["Inkommet datum"] = pd.to_datetime(df["Inkommet datum"], errors="coerce")

# drop rows from 1-30 june 2025 (to get just 2 years: 1 june 2023 to 31 may 2025)
start_date = '2023-06-01'
end_date = '2025-06-01' # if i set 2025-05-31 i only get up until 2025-05-30 23:43:07.590000
mask = (df['Inkommet datum'] > start_date) & (df['Inkommet datum'] <= end_date)

df = df.loc[mask]

print("\n--- Cleaning Date and Time ---")
print("first and last entry within valid the time frame:")
print(df['Inkommet datum'].min(), df['Inkommet datum'].max())

# extract date (or time) only
df["year"] = df["Inkommet datum"].dt.year
df["month"] = df["Inkommet datum"].dt.month
df["day"] = df["Inkommet datum"].dt.day
df["weekday"] = df["Inkommet datum"].dt.day_name()
df["hour"] = df["Inkommet datum"].dt.hour

# group into period 1 and 2
df["custom_year"] = df["Inkommet datum"].apply(
    lambda x: x.year if x.month >= 6 else x.year - 1
) # 6 refers to the month of june and 1 year from that

df["year_label"] = "June " + df["custom_year"].astype(str) + "–May " + (df["custom_year"] + 1).astype(str)

datetime_after = len(df)
datetime_removed = datetime_before - datetime_after
print(f"Removed {datetime_removed} rows outside the valid timeframe, {len(df)} total rows remaining.")

# =====================================
# === PRE PROCESSING OF COORDINATES ===

df["Koordinater_x"] = df["Koordinater_x"].replace(0, np.nan)
df["Koordinater_Y"] = df["Koordinater_Y"].replace(0, np.nan)

before_count = len(df)
df = df.dropna(subset=["Koordinater_x", "Koordinater_Y"]) # drop rows where either coordinate is missing
after_count = len(df)
removed = before_count - after_count
print("\n--- Cleaning coordinates ---")
print(f"Removed {removed} rows without valid coordinates, {len(df)} total rows remaining.") # Removed 84213 rows without valid coordinates.

# =======================================
# === DUPLICATE COORDINATES + FRITEXT ===

duplicates_before = len(df)

# keep first occurence and then remove duplicates if same content in Koordinater_x", "Koordinater_Y" and "Fritext"
df = df.drop_duplicates(subset=["Koordinater_x", "Koordinater_Y", "Fritext"])

duplicates_after = len(df)
print("\n--- Cleaning duplicates ---")
print(f"Removed {duplicates_before - duplicates_after} duplicate rows based on coordinates and Fritext.")

# =================================
# === PRE PROCESSING OF FRITEXT ===

freetext_before = len(df)

# remove empty or whitespace only rows
df = df[df["Fritext"].notna() & df["Fritext"].str.strip().ne("")]

# remove rows with numbers or symbols (incl emojis) and no text, in other words remove all rows without at least one letter
import re
df = df[df["Fritext"].apply(lambda x: re.search(r"[a-zA-ZåäöÅÄÖ]", str(x)) is not None)]

# make all text lowercase
#df["clean_Fritext"] = df["Fritext"].str.lower                                                     # removed this too to help issue with BERTopic and -1

# clean up text that includes certain symbols or emojis by removing them but keeping the text
#df["clean_Fritext"] = df["clean_Fritext"].str.replace(r"[^a-zA-ZåäöÅÄÖ0-9\s]", "", regex=True)    # used this initially, but it might be to aggressive for TOPICmodel
df["clean_Fritext"] = df["clean_Fritext"].str.replace(r"[^\w\s.,!?åäöÅÄÖ]", "", regex=True)        # so keeping normal symbols but removing emojis might be better

# remove standalone 'k' as a word
df["clean_Fritext"] = df["clean_Fritext"].str.replace(r"\bk\b", "", regex=True)

# remove dn trädgård och dn trädgårdl
unwanted_phrases = [
    r"\bdn\s+trädgård(l)?\b",                    # add to list if necessary
]
for phrase in unwanted_phrases:
    df["clean_Fritext"] = df["clean_Fritext"].str.replace(phrase, "", flags=re.IGNORECASE, regex=True)

df["clean_Fritext"] = df["clean_Fritext"].str.replace(r"\s{2,}", " ", regex=True).str.strip()   # remove any extra whitespace

# remove standalone numbers and IDs where there is a mix of numbers and letters (e.g. abc123)
df["clean_Fritext"] = df["clean_Fritext"].apply(
    lambda x: " ".join([
        word for word in x.split()
        #if not re.fullmatch(r"(?=.*[a-zA-ZåäöÅÄÖ])(?=.*\d)[a-zA-ZåäöÅÄÖ0-9]+|\d+", word)         # removed this too to help issue with BERTopic and -1
        if not re.fullmatch(r"\d+", word)                                                         # keeping only numbers without any letters mixed in
    ])
)

# remove any now empty rows
df = df[df["clean_Fritext"].str.strip().ne("")]

freetext_after = len(df)
freetext_removed = freetext_before - freetext_after

print("\n--- Cleaning Fritext ---")
print(f"Removed {freetext_removed} rows without valid text in 'Fritext', {len(df)} total rows remaining.")

# ================================
# === PRE PROCESSING OF EXTENT ===

municipality = gpd.read_file(f"{input_directory}\\Output\\Kommun_Stadskartan_SWEREF99TM.gpkg").to_crs("EPSG:3006")
municipality_geom = municipality.geometry.iloc[0]

pts = gpd.GeoDataFrame(
    df, geometry=gpd.points_from_xy(
        df['Koordinater_x'],
        df['Koordinater_Y']
    ),
    crs=4326)
pts = pts.to_crs("EPSG:3006")

pts.to_file("data/tyck_till_output/tycktill.gpkg", layer="all_points", driver="GPKG", mode="w")

within_before = len(pts)
pts = pts[pts.geometry.within(municipality_geom)].copy()
within_after = len(pts)
removed_outside = within_before - within_after

df = df.loc[pts.index]

print("\n--- Filtering by municipality ---")
print(f"Removed {removed_outside} rows with coordinates outside the municipality boundary, {len(df)} total rows remaining.")

df.to_excel("data/cleaned_dataset.xlsx")


# =========================================================
# === create layers for tycktill.gpkg + summarize stats ===

parks = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base").to_crs(3006)

# get points in parks only
pts_in_parks = gpd.sjoin(pts, parks, how="inner", predicate="within").drop(columns='index_right', errors='ignore')
pts_in_parks.to_file("data/tyck_till_output/tycktill.gpkg", layer="pts_in_parks", driver="GPKG", mode="w")

# tycktill stats per park
summary = pts_in_parks.groupby('group').agg(
    num_points=('geometry', 'count'),
    unique_comments=('Fritext', 'nunique'),
).reset_index()

summary['park_area'] = summary['group'].map(parks.set_index('group')['park_area'])
summary['pts_per_hectare'] = summary['num_points'] / (summary['park_area'] / 10000)

parks = parks.merge(summary, on='group', how='left')

# category stats per park
pts_in_parks['Kategori'] = pts_in_parks['Kategori'].fillna('Okänd')
kategori_counts = pts_in_parks.groupby(['group', 'Kategori']).size().unstack(fill_value=0).reset_index()
parks = parks.merge(kategori_counts, on='group', how='left')

# normalize category counts by total number of points in each park
kategori_cols = kategori_counts.columns.difference(['group'])  # all category columns

#for col in kategori_cols:
#    parks[f'{col}_rel'] = parks[col] / parks['num_points']

for col in kategori_cols:
    parks[f'{col}_rel'] = parks.apply(
        lambda row: row[col] / row['num_points'] if pd.notna(row[col]) and pd.notna(row['num_points']) and row['num_points'] > 0 else 0,
        axis=1
    )

parks.to_file("data/tyck_till_output/tycktill.gpkg", layer="stats_per_park", driver="GPKG", mode="w")

# count entries per Kategori inside and outside parks
pts['in_park'] = pts.index.isin(pts_in_parks.index)

kategori_in = pts[pts['in_park']].groupby('Kategori').size()
kategori_out = pts[~pts['in_park']].groupby('Kategori').size()
kategori_total = pts.groupby('Kategori').size()

kategori_summary = pd.DataFrame({
    'In parks': kategori_in,
    'Outside parks': kategori_out,
    'Total': kategori_total
}).fillna(0).astype(int).reset_index()

print("\n--- Entry count by Kategori ---")
print(kategori_summary)


# ==============
# === OUTPUT ===

# --- Before cleaning ---
# Initially 414481 total rows.
#
# --- Cleaning Date and Time ---
# first and last entry within valid the time frame:
# 2023-06-01 00:06:55.153000 2025-05-31 23:36:03.390000
# Removed 20277 rows outside the valid timeframe, 394204 total rows remaining.
#
# --- Cleaning coordinates ---
# Removed 84213 rows without valid coordinates, 309991 total rows remaining.
#
# --- Cleaning duplicates ---
# Removed 11005 duplicate rows based on coordinates and Fritext.
#
# --- Cleaning Fritext ---
# Removed 653 rows without valid text in 'Fritext', 298333 total rows remaining.
#
# --- Filtering by municipality ---
# Removed 235 rows with coordinates outside the municipality boundary, 298044 total rows remaining.
#
# --- Entry count by Kategori ---
#                   Kategori  In parks  Outside parks   Total
# 0                  Ansökan         0              3       3
# 1  Arbetsorder ska skickas        10             33      43
# 2                    Beröm       301           1620    1921
# 3               Felanmälan     75835         198283  274118
# 4             Fordonsflytt         2             27      29   # there were almost 80 000 in Fordonsflytt but almost none have coordinates
# 5                    Fråga      1158           6712    7870
# 6                      Idé       829           4976    5805
# 7                 Klagomål      1404           6823    8227
# 8         Ordningsstörning         7             11      18
# 9           Remiss skickad         2             62      64
#
# Process finished with exit code 0









