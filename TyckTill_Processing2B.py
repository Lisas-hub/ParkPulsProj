
# >>> SENTIMENT MODEL per kategori <<<

from collections import Counter
import geopandas as gpd
import os
import pandas as pd
import numpy as np


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
    model="KBLab/robust-swedish-sentiment-multiclass",
    top_k=None  # Get all class scores, not just the top one
)

def prepare_inputs(texts, tokenizer, max_length=512):
    return tokenizer(
        texts,
        truncation=True,
        max_length=max_length,
        padding=False,         # Or True/“max_length” if batching
        return_tensors=None    # Set to "pt" if feeding directly to model
    )

# Apply to your DataFrame column
texts = df["clean_Fritext"].astype(str).tolist()

# apply sentiment analysis
# Run through the sentiment pipeline directly — it handles truncation automatically
sentiments = model(texts, truncation=True)
#sentiments = model(texts)
df["sentiment_label"] = [s[0]["label"] for s in sentiments]
df["sentiment_score"] = [s[0]["score"] for s in sentiments]
df["sentiment_all"] = sentiments # keep all class scores (positive/neutral/negative)
df.to_excel(f"{output_folder}/tycktill_with_sentiment_{kategori_input}.xlsx", index=False)

# ================
# make point layer

tycktill_pts_with_sentiment = gpd.GeoDataFrame(
    df, geometry=gpd.points_from_xy(
        df['Koordinater_x'],
        df['Koordinater_Y']
    ),
    crs=4326)

tycktill_pts_with_sentiment.to_file(f"{output_folder}/tycktill_{kategori_input}.gpkg", layer=f"tycktill_pts_with_sentiment_{kategori_input}", driver="GPKG", mode="w")


