import re

import snowballstemmer

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_stemmer = snowballstemmer.stemmer("english")


def stem_tokenize(text: str) -> list[str]:
    """Lowercase, extract alphanumeric tokens, and stem them.

    Stemmed so "vaccine"/"vaccines"/"vaccinated" and "contradict"/
    "contradiction" match under plain keyword overlap - without this, exact
    tokens treat inflected forms of the same word as unrelated, which matters
    most for abstract/causal claims (a claim about "vaccines" scoring
    evidence titled "vaccine misinformation" as a weaker match than it
    should be). Shared by BM25 ranking and Wikipedia's in-article passage
    scoring so both use the same notion of "matching word".
    """
    return _stemmer.stemWords(_TOKEN_RE.findall(text.lower()))
