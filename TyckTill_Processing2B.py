
# >>> SENTIMENT MODEL per kategori <<<

from collections import Counter
import geopandas as gpd
import os
import pandas as pd
from tqdm import tqdm


# =====================================
# set up for saving in the right folder

kategori_input = input("☆☆☆ Enter the Kategori used in the first script (e.g. Felanmälan): ")

if not kategori_input:
    print("❌ enter a valid kategori ❌")
    exit()

output_folder = os.path.join("data", "tyck_till_output", "per_kategori")

# ======================
# load processed dataset
df = pd.read_excel(f"{output_folder}/tycktill_with_lemmas_{kategori_input}.xlsx", parse_dates=["Inkommet datum"])

# ======================================================================================
# truncate text before sentiment (because there is a limit to text length with the model

from transformers import AutoTokenizer, pipeline

tokenizer = AutoTokenizer.from_pretrained("KBLab/robust-swedish-sentiment-multiclass")

# ================================================================
# ============ PRETRAINED LANGUAGE MODEL FOR SWEDISH =============
# ========== KBLab/robust-swedish-sentiment-multiclass ===========
# https://huggingface.co/KBLab/robust-swedish-sentiment-multiclass

from transformers import pipeline
from transformers import AutoTokenizer

model_name = "KBLab/robust-swedish-sentiment-multiclass"
tokenizer = AutoTokenizer.from_pretrained(model_name)

# load model
model = pipeline(
    "text-classification",
    model=model_name,
    top_k=None  # Get all class scores, not just the top one
)

texts = df["clean_Fritext"].astype(str).tolist()

batch_size = 32                  # <<< adjust here <<<

# lists to store results
all_labels = []
all_scores = []
all_outputs = []

print("\n--- Running sentiment analysis ---")
for i in tqdm(range(0, len(texts), batch_size)):
    batch_texts = texts[i:i+batch_size]
    batch_output = model(batch_texts, truncation=True)

    # first label and score from each result
    all_labels.extend([s[0]["label"] for s in batch_output])
    all_scores.extend([s[0]["score"] for s in batch_output])
    all_outputs.extend(batch_output)

# add results to DataFrame
df["sentiment_label"] = all_labels
df["sentiment_score"] = all_scores
df["sentiment_all"] = all_outputs

df.to_excel(f"{output_folder}/with_sentiment_{kategori_input}.xlsx", index=False)
print("\n✅ Sentiment analysis completed and saved.")

# ================
# make point layer

tycktill_pts_with_sentiment = gpd.GeoDataFrame(
    df, geometry=gpd.points_from_xy(
        df['Koordinater_x'],
        df['Koordinater_Y']
    ),
    crs=4326)

tycktill_pts_with_sentiment.to_file(f"{output_folder}/tycktill_{kategori_input}.gpkg", layer=f"tycktill_pts_with_sentiment_{kategori_input}", driver="GPKG", mode="w")


