
import pandas as pd
import geopandas as gpd
from collections import Counter

import nltk # good for english
import stanza # best for swedish?

# nltk
from nltk.stem import SnowballStemmer # there are multiple stemmers, another is PorterStemmer but it is older?
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

#nltk.download('punkt')
#nltk.download('stopwords')

# stanza
#stanza.download('sv')

stop_words = set(stopwords.words('swedish'))
stemmer = SnowballStemmer("swedish")

nlp = stanza.Pipeline(lang='sv')

tycktill_df = pd.read_excel(r'C:\Users\lisajos\QGIS_Projects\TyckTill\NEW\TyckTill_2023-01-01_2024-12-31.xlsx')
tycktill_df_subset = tycktill_df.head(50).copy()


# ===========================
# === most frequent words ===
all_words = []
for i, row in enumerate(tycktill_df_subset["Fritext"]):
    print(f"Processing row {i + 1} of {len(tycktill_df_subset)}", flush=True)

    doc = nlp(row) # runs text through Stanzas NLP pipeline (which is tokenizer, POS tagger, lemmatizer)
    for sentence in doc.sentences:
        for word in sentence.words:
            if word.upos != "PUNCT" and word.text.casefold() not in stop_words:
                all_words.append(word.lemma)

# Show the top 20 most common words
word_freq = Counter(all_words)
print(word_freq.most_common(20))

lower_fd = nltk.FreqDist([w.lower() for w in word_freq])

# ==================================
# === word frequency by Kategori ===
category_word_freqs = {}

for category, group in tycktill_df_subset.groupby("Kategori"):
    all_words = []
    for text in group["Fritext"]:
        doc = nlp(text)
        for sentence in doc.sentences:
            for word in sentence.words:
                if word.upos != "PUNCT" and word.text.casefold() not in stop_words:
                    all_words.append(word.lemma)

    word_freq = Counter(all_words)
    category_word_freqs[category] = word_freq

# Example: top 10 words in one category
for category, freqs in category_word_freqs.items():
    print(f"Category: {category}")
    print(freqs.most_common(10))
    print()

# ===================================
# === word frequency by date/time ===
import pandas as pd
import matplotlib.pyplot as plt
from collections import defaultdict

tycktill_df_subset["Inkommet datum"] = pd.to_datetime(tycktill_df_subset["Inkommet datum"], errors='coerce')
tycktill_df_subset["DateOnly"] = tycktill_df_subset["Inkommet datum"].dt.floor("D")

print(tycktill_df_subset["DateOnly"].head(5))
#print(tycktill_df_subset[["Inkommet datum", "DateOnly"]].head(5))



# *********