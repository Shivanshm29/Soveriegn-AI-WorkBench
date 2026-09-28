"""Tests for Industrial Photo Inspector and candidate terminology enforcement."""

from backend.app.vision.industrial_inspector import IndustrialPhotoInspector
from backend.app.vision.schemas import (
    ConfidenceAssessment,
    ConfidenceLevel,
    EngineeringEvidenceType,
)


def test_candidate_language_sanitization():
    """Verify that definitive diagnostic claims are downgraded to candidate observations."""
    inspector = IndustrialPhotoInspector()

    raw_text = "The pump casing is broken and completely corroded. It is defective and unsafe."
    sanitized = inspector.sanitize_engineering_language(raw_text)

    assert "broken" not in sanitized
    assert "shows visible damage candidate" in sanitized
    assert "shows visible corrosion candidate" in sanitized
    assert "displays candidate irregularity" in sanitized
    assert "exhibits visual anomaly requiring physical safety evaluation" in sanitized


def test_candidate_finding_mandatory_qualifiers():
    """Verify that findings mandate candidate terminology in titles and human verification recommendations."""
    inspector = IndustrialPhotoInspector()
    conf = ConfidenceAssessment(value=0.7, level=ConfidenceLevel.MEDIUM, rationale="Visual texture match")

    finding = inspector.create_candidate_finding(
        title="Corrosion Zone Detected",
        description="Visible reddish oxidation observed on flange surface.",
        finding_type="corrosion_candidate",
        confidence=conf,
    )

    # Must contain candidate qualifier
    assert any(q in finding.title.lower() for q in ["candidate", "visible indication", "possible", "observed"])
    assert "requires on-site qualified human engineering verification" in finding.recommendation.lower()


def test_separation_of_observation_interpretation_uncertainty():
    """Verify that observation, interpretation, and uncertainty are strictly separated."""
    inspector = IndustrialPhotoInspector()
    conf = ConfidenceAssessment(value=0.8, level=ConfidenceLevel.HIGH, rationale="Direct camera view")

    obs = inspector.create_candidate_observation(
        region_id="reg_flange_01",
        observed_visual_features="Discolored brownish-red circular texture on lower flange edge.",
        inferred_interpretation="Visual appearance is consistent with surface oxidation candidate.",
        uncertainty_statement="2D photograph cannot determine metallurgical depth or pitting extent.",
        confidence=conf,
    )

    assert obs.observation == "Discolored brownish-red circular texture on lower flange edge."
    assert "candidate" in obs.interpretation.lower()
    assert "cannot determine" in obs.uncertainty.lower()
    assert obs.verification_required is True
    assert obs.verification_status == "PENDING_VERIFICATION"


def test_inspect_visual_anomalies_pipeline():
    """Test full anomaly inspection producing evidence, observations, and findings."""
    inspector = IndustrialPhotoInspector()
    features = [
        {
            "region_id": "reg_pipe_01",
            "type": "corrosion_candidate",
            "bounding_box": [50.0, 50.0, 200.0, 200.0],
            "description": "Reddish surface discoloration",
            "observation": "Discoloration patch at 50,50",
            "interpretation": "Possible surface corrosion candidate",
            "uncertainty": "Material thickness unknown",
            "confidence": 0.75,
            "rationale": "Color histogram deviation",
        }
    ]

    evs, obss, fnds = inspector.inspect_visual_anomalies(
        image_metadata={"dimensions": [800, 600]},
        detected_features=features,
        document_id="doc_pipe_001",
        source_hash="hash_pipe_001",
        page_number=1,
    )

    assert len(evs) == 1
    assert evs[0].evidence_type == EngineeringEvidenceType.DEFECT_CANDIDATE
    assert len(obss) == 1
    assert obss[0].region_id == "reg_pipe_01"
    assert len(fnds) == 1
    assert fnds[0].finding_type == "corrosion_candidate"
