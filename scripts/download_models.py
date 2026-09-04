"""Pre-fetch all ML models used by the pipeline so the first API request
isn't slowed down by cold downloads. Run once after `pip install`.
"""

import subprocess
import sys

from app.ml.model_registry import SPACY_MODEL_NAME, load_all


def main() -> None:
    subprocess.run([sys.executable, "-m", "spacy", "download", SPACY_MODEL_NAME], check=True)
    print("Loading SBERT / CrossEncoder / NLI models (downloads on first run)...")
    load_all()
    print("All models downloaded and cached.")


if __name__ == "__main__":
    main()
