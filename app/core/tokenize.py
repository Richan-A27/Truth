import re
import threading

import snowballstemmer

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# One stemmer per thread: a snowballstemmer instance keeps the word being
# stemmed as mutable state, so sharing one across threads corrupts it. That
# surfaced as "IndexError: string index out of range" in BM25 once claims
# began running concurrently - Wikipedia's passage scoring (event-loop thread)
# and BM25 (worker thread) were stemming through the same instance at once.
_local = threading.local()


def _stemmer():
    stemmer = getattr(_local, "stemmer", None)
    if stemmer is None:
        stemmer = _local.stemmer = snowballstemmer.stemmer("english")
    return stemmer


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
    return _stemmer().stemWords(_TOKEN_RE.findall(text.lower()))
