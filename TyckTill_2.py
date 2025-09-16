
import pandas as pd
import geopandas as gpd
from collections import Counter

import nltk # good for english
import stanza # best for swedish?

# nltk
from nltk.stem import SnowballStemmer # there are multiple stemmers, another is PorterStemmer but it is older?
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

nltk.download('punkt')
nltk.download('stopwords')

# stanza
stanza.download('sv')

# =================
# === NLTK test ===

example_string = """Nu har sandlådan i Fatbursparken inte kunnat användas på över ett år. Man satt stängsel runt sandlådan april 2022 nu i slutet på maj 2023 har fortfarande inget hänt. Står på en skylt att man skall starta i maj 2023 så vi hoppas fortfarande att något händer väldigt snabbt med sandlådan. Det tråkiga är att de barn som går på förskolor runt här det finns en i Bofils båge bla annat inte har på ett år kunnat leka i sandlådan  Hoppas nu att man tar barnens lek på allvar och startar bygget nu de sista dagarna i maj eftersom planeringen har haft god tid på sig. Ser också framemot att barnen får tillbaka den ”druvklasen” som fanns i sandlådan men som också skulle repareras. Den var mycket populär att klättra i."""

sent_tokenize(example_string) # splits text into sentences
word_tokenize(example_string) # splits text into words

words = word_tokenize(example_string)
words

# stop words - common words of little significance
stop_words = set(stopwords.words('swedish'))
filtered_list = []

for word in example_string:
    if word.casefold() not in stop_words:
         filtered_list.append(word)

filtered_list

# stemming - reducing a word to it's root, ex 'katter' to 'katt'
stemmer = SnowballStemmer("swedish")
#stemmer = PorterStemmer() # older than SnowballStemmer

stemmed_words = [stemmer.stem(word) for word in words]
stemmed_words # gives a few bad results (under- and overstemming) like allv (for allvar) and sandlådan (should be sandlåd ?)


# ===================
# === stanza test ===

nlp = stanza.Pipeline(lang='sv')

text = """Nu har sandlådan i Fatbursparken inte kunnat användas på över ett år. Man satt stängsel runt sandlådan april 2022 nu i slutet på maj 2023 har fortfarande inget hänt. Står på en skylt att man skall starta i maj 2023 så vi hoppas fortfarande att något händer väldigt snabbt med sandlådan. Det tråkiga är att de barn som går på förskolor runt här det finns en i Bofils båge bla annat inte har på ett år kunnat leka i sandlådan  Hoppas nu att man tar barnens lek på allvar och startar bygget nu de sista dagarna i maj eftersom planeringen har haft god tid på sig. Ser också framemot att barnen får tillbaka den ”druvklasen” som fanns i sandlådan men som också skulle repareras. Den var mycket populär att klättra i."""

doc = nlp(text) # runs text through Stanzas NLP pipeline (which is tokenizer, POS tagger, lemmatizer)
for sentence in doc.sentences:
    for word in sentence.words:
        print(f"{word.text}\t{word.lemma}\t{word.upos}")

# use the whole Fritext column
tycktill_df = pd.read_excel(r'C:\Users\lisajos\QGIS_Projects\TyckTill\NEW\Rådata\Raw_TyckTill_2023-01-01_2024-12-31.xlsx')

# word frequency
all_words = []
for row in tycktill_df["Fritext"]:
    doc = nlp(row)
    for sentence in doc.sentences:
        for word in sentence.words:
            if word.upos != "PUNCT" and word.text.casefold() not in stop_words:
                all_words.append(word.lemma)
Counter(all_words).most_common(20)


