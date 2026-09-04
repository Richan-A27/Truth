import pytest


@pytest.fixture
def sample_evidence_docs():
    from app.schemas.evidence import EvidenceDocument

    return [
        EvidenceDocument(
            source="wikipedia",
            title="Eiffel Tower",
            url="https://en.wikipedia.org/wiki/Eiffel_Tower",
            snippet="The Eiffel Tower is a wrought-iron lattice tower in Paris, France.",
        ),
        EvidenceDocument(
            source="wikipedia",
            title="Bicycle",
            url="https://en.wikipedia.org/wiki/Bicycle",
            snippet="A bicycle, also called a bike, is a human-powered vehicle.",
        ),
    ]
