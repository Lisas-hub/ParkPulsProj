
# >>> SENTIMENT MODEL per kategori <<<

from collections import Counter
import geopandas as gpd
import os
import pandas as pd
from tqdm import tqdm
from shapely.geometry import Point
from transformers import AutoTokenizer, pipeline

#             OLD SETUP
# =====================================
# set up for saving in the right folder

#kategori_input = input("☆☆☆ Enter the Kategori used in the first script (e.g. Felanmälan): ")

#if not kategori_input:
#    print("❌ enter a valid kategori ❌")
#    exit()

#output_folder = os.path.join("data", "tycktill_output")

# ======================
# load processed dataset
#df = pd.read_excel(f"{output_folder}/tycktill_with_lemmas_{kategori_input}.xlsx", parse_dates=["Inkommet datum"])


#            NEW SETUP
# ===============================
# === LOAD PRE-PROCESSED DATA ===

df = pd.read_excel("data/cleaned_dataset.xlsx")

# ======================
# create geometry column

df["geometry"] = df.apply(lambda row: Point(row["Koordinater_x"], row["Koordinater_Y"]), axis=1)
df_geo = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326").to_crs("EPSG:3006")

# =================================================
# prepp for filtering inside or outside parks later
parks = gpd.read_file("data/VARIABLES_NEW.gpkg", layer="VARIABLES_base")

subset_within_parks = gpd.sjoin(df_geo, parks, how="inner", predicate="within")
df_geo["in_park"] = df_geo.index.isin(subset_within_parks.index)

# ============================================
# subset by parks and a limited number of rows

# subset dataset to begin with before committing to processing all 300000+ rows
kategori_filter = "Remiss skickad"
#in_park_filter = True
# ^^RERUN? Update here!^^

subset_df = df_geo[
    (df_geo["Kategori"] == kategori_filter) #&
    #(df_geo["in_park"] == in_park_filter)
].copy()

# =================================================================
# set up for saving figures based on number of points in the subset

output_folder = f"data/tycktill_output/sentiments"
os.makedirs(output_folder, exist_ok=True)


# ================================================================
# ============ PRETRAINED LANGUAGE MODEL FOR SWEDISH =============
# ========== KBLab/robust-swedish-sentiment-multiclass ===========
# https://huggingface.co/KBLab/robust-swedish-sentiment-multiclass

tokenizer = AutoTokenizer.from_pretrained("KBLab/robust-swedish-sentiment-multiclass")

model_name = "KBLab/robust-swedish-sentiment-multiclass"
tokenizer = AutoTokenizer.from_pretrained(model_name)

# load model
model = pipeline(
    "text-classification",
    model=model_name,
    top_k=None  # get all class scores, not just the top one
)

texts = subset_df["clean_Fritext"].astype(str).tolist()

batch_size = 32                  # <<< adjust here <<<

# lists to store results
all_labels = []
all_scores = []
all_outputs = []

print("\n--- Running sentiment analysis ---")
for i in tqdm(range(0, len(texts), batch_size)):
    batch_texts = texts[i:i+batch_size]
    batch_output = model(batch_texts, truncation=True) # truncate text before sentiment (because there is a limit to text length with the model

    # first label and score from each result
    all_labels.extend([s[0]["label"] for s in batch_output])
    all_scores.extend([s[0]["score"] for s in batch_output])
    all_outputs.extend(batch_output)

# add results to DataFrame
subset_df["sentiment_label"] = all_labels
subset_df["sentiment_score"] = all_scores
subset_df["sentiment_all"] = all_outputs

subset_df.to_excel(f"{output_folder}/tycktill_with_sentiment_{kategori_filter}.xlsx", index=False)
print("\n✅ Sentiment analysis completed and saved.")

# ================
# make point layer

tycktill_pts_with_sentiment = gpd.GeoDataFrame(
    subset_df, geometry=gpd.points_from_xy(
        subset_df['Koordinater_x'],
        subset_df['Koordinater_Y']
    ),
    crs=4326)

tycktill_pts_with_sentiment.to_file(f"{output_folder}/tycktill_{kategori_filter}.gpkg", layer=f"tycktill_pts_with_sentiment_{kategori_filter}", driver="GPKG", mode="w")


