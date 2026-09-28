# Phase 7 Implementation Report — Engineering Drawing & Industrial Vision Agent

## Executive Summary

Phase 7 of the Sovereign On-Premise Agentic AI Workbench implements a fully local **Engineering Drawing & Industrial Vision Agent**. This agent performs structured visual analysis of engineering drawings (DWG/PDF/image formats), technical diagrams, and industrial equipment photographs using only on-premise resources — no cloud vision API, no external OCR service, no internet connectivity.

The agent enforces strict **zero-hallucination discipline** (Section 9): every dimension is extracted deterministically from text with regex, every finding is labelled a *candidate* requiring physical verification, and every evidence object is cryptographically tied to its source document via SHA-256 hash. The Phase 5 Risk/Policy/Approval system remains fully active and cannot be bypassed by any vision operation.

---

## 1. Package Location

| Module | Path |
|---|---|
| Vision package root | `backend/app/vision/` |
| Schemas | `backend/app/vision/schemas.py` |
| Dimension extractor | `backend/app/vision/dimension_extractor.py` |
| Industrial inspector | `backend/app/vision/industrial_inspector.py` |
| Image preprocessor & tiler | `backend/app/vision/preprocessing.py` |
| Visual region detector | `backend/app/vision/region_detector.py` |
| Evidence verifier | `backend/app/vision/verifier.py` |
| Main agent | `backend/app/vision/agent.py` |
| Tool contracts | `backend/app/vision/tools.py` |
| Structured errors | `backend/app/vision/errors.py` |

---

## 2. Evidence Schemas (schemas.py)

All Phase 7 data contracts are Pydantic models with strict field validation.

### EngineeringEvidenceType (Enum)
Categories of visual evidence: DIMENSION, ANNOTATION, SYMBOL, COMPONENT, LABEL, TABLE, DRAWING_VIEW, TITLE_BLOCK, PHOTOGRAPH, DEFECT_CANDIDATE, GEOMETRIC_FEATURE, UNKNOWN.

### ConfidenceLevel / ConfidenceAssessment
- Discrete tiers: HIGH (>=0.80), MEDIUM (>=0.50), LOW (>0.0), UNKNOWN (0.0).
- Every confidence object carries a numeric value, categorical level, and human-readable rationale.

### DimensionItem
Structured extracted dimension: raw_text, value (float or None), unit, tolerance, feature_type (diameter/radius/thread/angular/linear), bounding_box, confidence.

### VisualRegion
Identified structural region: region_type (title_block, drawing_body, dimensions, annotations, symbols, etc.), bounding_box, text_content, sub_elements, confidence.

### ImageTile
Metadata for a high-resolution sub-region: tile_path, bounding_box in original image coordinates, tile_col, tile_row, original_dimensions.

### EngineeringEvidence
Primary auditable evidence object: evidence_id, document_id, source_hash (SHA-256), page_number, region_id, evidence_type, bounding_box, observation, extracted_text, visual_features, confidence, extraction_method.

### VisualObservation
Strictly separates what was OBSERVED (visual facts), INTERPRETED (model hypotheses), and UNCERTAIN (explicit uncertainty statement). Always marked verification_required=True.

### EngineeringFinding
High-level finding: title, description, finding_type, severity (INFORMATIONAL/LOW/MEDIUM/HIGH), evidence_ids, confidence, recommendation. Findings MUST NOT use certified diagnostic language.

### EngineeringVisionResult
Complete auditable result: task_id, document_id, source_hash, analyzed_regions, evidence, observations, findings, uncertainties, verification_status, verification_summary, model_used, processing_metadata.

---

## 3. Deterministic Dimension Extractor (dimension_extractor.py)

Zero-hallucination extraction — no LLM is used for numeric values.

- Regex Patterns: Detects diameter (O, DIA, diameter symbol), radius (R, RAD), thread (M8x1.25), quantity multipliers (4x), angular (45 deg), and units (mm, in, cm, ft).
- Tolerance Parsing: Symmetric (+-0.05), bilateral (+0.1/-0.0), and ISO fit class (H7, g6).
- Ambiguity Rule (Section 9): Any text with approximate markers (approx, ~, ?, unclear, blurred) produces value=None with confidence.level=LOW and explicit uncertainty.
- Failure Modes: Unreadable tokens return value=None; never guessed or interpolated.
- to_engineering_evidence(): Converts DimensionItem list into auditable EngineeringEvidence objects bound to document_id and source_hash.

---

## 4. Industrial Photograph Inspector (industrial_inspector.py)

Enforces candidate language for all industrial visual findings.

- CERTIFIED_CLAIMS_MAP: Forbidden diagnostic terms (corroded, cracked, failed, unsafe, leaking) are auto-replaced with candidate equivalents.
- sanitize_engineering_language(): Post-processes model output to enforce candidate framing.
- create_candidate_observation(): Factory producing VisualObservation with strict separation of observation, interpretation, and uncertainty.
- inspect_visual_anomalies(): Converts raw detected features into typed EngineeringEvidence, VisualObservation, and EngineeringFinding objects. All findings carry recommendation: "Requires qualified human inspection and verification."

---

## 5. Image Preprocessor & Tiler (preprocessing.py)

All image manipulation is fully local using Pillow (PIL).

- validate_image(): Checks file existence, readable format, enforces dimension limits (raises OversizedImageError).
- preprocess(): Applies local EXIF-orientation correction, converts to RGB, applies adaptive histogram equalization for contrast normalization.
- generate_tiles(): For large drawings exceeding tile_size (default 1000px), splits into tile_col x tile_row grid, saves to data/cache/tiles/, raises TileGenerationError if tile count exceeds maximum (25). Returns List[ImageTile] with bounding boxes in original image coordinates.

---

## 6. Visual Region Detector (region_detector.py)

Deterministic spatial heuristic region classification — no LLM involved.

detect_regions() classifies drawing areas by bounding-box geometry heuristics:
- title_block: Bottom-right quadrant with high OCR text density and low vertical extent.
- dimensions: Regions with high numeric character density matching dimension patterns.
- drawing_body: Central large spatial region.
- annotations / notes: Text-rich, narrow regions.
- photograph / diagram: Low text density, large area.
- unknown: Regions not matching any classifier.

Returns List[VisualRegion] preserving text content, sub-elements (OCR tokens), and confidence scores.

---

## 7. Visual Evidence Verifier (verifier.py)

Fully deterministic post-processing verification (Section 16).

Runs 6 independent checks on every EngineeringVisionResult:

| Check | Rule |
|---|---|
| Source hash integrity | result.source_hash must be present and match expected_source_hash |
| Region bounding boxes | [x0, y0, x1, y1] with x0<=x1, y0<=y1, within image dimensions |
| Evidence bounding boxes | Same geometry rules; evidence source_hash must match result |
| Observation -> Evidence references | Every evidence_ref in VisualObservation must exist in evidence list |
| Finding -> Evidence references | Every evidence_id in EngineeringFinding must exist |
| Candidate terminology | Finding titles must not use "certified safe", "guaranteed broken", or "confirmed defect" |

Produces VerificationReport(is_valid, status, total_checks, passed_checks, failed_checks, warnings) and writes status back to EngineeringVisionResult directly.

---

## 8. Engineering Vision Agent (agent.py)

The EngineeringVisionAgent is the top-level coordinator integrating all Phase 7 components.

### Pipeline: process_image(image_path, ...)

1. validate_image -> compute_source_hash -> check_cache
2. preprocess (PIL/local)
3. generate_tiles (if large drawing)
4. local OCR (LocalOCREngine from Phase 6)
5. PromptInjectionDefense.scan_for_injection_patterns (on OCR text)
6. VisualRegionDetector.detect_regions
7. DimensionExtractor.extract_from_text (for dimension/drawing_body regions)
8. IndustrialPhotoInspector.inspect_visual_anomalies (for photograph/diagram regions)
9. EngineeringVisionAgent._invoke_local_vlm (optional, if ModelRuntime available)
10. VisualEvidenceVerifier.verify_result (deterministic)
11. cache result -> return EngineeringVisionResult

### Pipeline: process_pdf_drawing(pdf_path, page_number, ...)

Uses Phase 6 PDFProcessor to render the target page to a local PNG, then delegates to process_image(). Full sovereignty maintained — no cloud rendering.

### Model Resolution: resolve_vision_model()

Dynamically resolves the vision model through ModelRegistry.resolve() without hard-coding any model ID. Tries capability chains: vision.engineering_analysis -> vision.image_understanding -> vision.document_analysis -> visual_reasoning. Falls back to TaskRouter if registry resolution fails.

### Local VLM Call: _invoke_local_vlm()

- Evidence-first isolated prompt with explicit security constraints embedded in prompt text.
- OCR text injected strictly as DATA with injection quarantine markers.
- Output sanitized by sanitize_engineering_language() before returning.
- Empty output guard: If model returns None or empty content (e.g. Qwen3 thinking-mode exhaustion), returns None gracefully without crashing.
- max_tokens=400 to prevent token budget overruns.

### Source Hash Cache

In-memory Dict[str, EngineeringVisionResult] keyed by {source_hash}_{options}_{user_focus}. Same image + same options returns cached result in O(1).

---

## 9. Vision Tools (tools.py)

Five ToolContract objects registered into ToolRegistry via register_vision_tools():

| Tool ID | Capabilities |
|---|---|
| engineering_drawing_analyze | engineering_drawing_analysis, vision.engineering_analysis, dimension_extraction |
| industrial_image_inspect | industrial_inspection, vision.image_understanding, candidate_defect_detection |
| image_preprocess_tile | image_tiling, image_preprocessing, region_extraction |
| visual_region_detect | visual_region_detection, layout_segmentation |
| verify_visual_evidence | visual_evidence_verification, deterministic_verification |

All tools are risk_level="LOW", requires_approval=False, enabled=True.

---

## 10. Vision Agent Registry Integration

- Agent ID: vision_agent
- Phase 7 Capabilities added: engineering_drawing_observations, engineering_drawing_analysis, vision.engineering_analysis, vision.image_understanding, industrial_inspection, candidate_defect_detection, dimension_extraction
- Dispatch logic in backend/app/orchestration/execution.py routes vision_agent tasks with image files to EngineeringVisionAgent before falling back to Phase 6 MultimodalDocumentPipeline.

---

## 11. Zero-Hallucination Discipline (Section 9)

| Rule | Enforcement |
|---|---|
| Numeric dimensions extracted only by deterministic regex | DimensionExtractor — no LLM for values |
| Ambiguous/unreadable values -> value=None | AMBIGUOUS_MARKERS regex triggers None |
| Findings labelled as candidates only | CERTIFIED_CLAIMS_MAP sanitization |
| All VLM output sanitized before evidence injection | sanitize_engineering_language() |
| Every evidence object cryptographically bound to source | source_hash (SHA-256) on every EngineeringEvidence |
| Human verification always required | verification_required=True on all outputs |
| Agent cannot certify engineering safety | Verifier rejects "certified safe" / "confirmed defect" language |

---

## 12. Prompt Injection Defense

All OCR text from images is scanned through PromptInjectionDefense.scan_for_injection_patterns() before VLM prompt inclusion. Detected patterns are:
- Flagged as uncertainties on the result.
- Treated as inert DATA, never executed.
- Explicitly labelled in VLM prompt with [UNTRUSTED DOCUMENT DATA] framing.

---

## 13. Resource Limits

| Limit | Default | Error Raised |
|---|---|---|
| Maximum tiles per image | 25 | TileGenerationError |
| Maximum VLM calls per pipeline invocation | 5 | VisionResourceLimitError |
| Maximum image dimension | Configurable | OversizedImageError |
| VLM max tokens per call | 400 | (server-enforced) |

---

## 14. Structured Error Hierarchy

All Phase 7 errors extend VisionProcessingError(Exception):

| Exception | Raised When |
|---|---|
| CorruptImageError | Image file is unreadable or truncated |
| UnsupportedImageFormatError | Image format not supported |
| OversizedImageError | Image dimensions exceed maximum |
| TileGenerationError | Tile count exceeds maximum |
| RegionDetectionError | Region extraction fails |
| VisualVerificationError | Verification checks fail |
| VisionResourceLimitError | VLM call or tile limits exceeded |
| VisionTimeoutError | Processing step times out |
| InvalidBoundingBoxError | Bounding box geometry invalid |
| MissingEvidenceError | Observation references non-existent evidence |
| MalformedModelOutputError | VLM output violates expected schema |

---

## 15. Empty Model Output Fix

A production-grade fix was applied to prevent Qwen3/Qwen2.5 models from producing empty output in vLLM thinking mode:

- local_openai_runtime.py: Automatically injects chat_template_kwargs: {enable_thinking: false} for Qwen3/Qwen2.5 model IDs.
- local_openai_runtime.py: Empty string content normalized to None; if both content and tool_calls absent, content defaults to "" as safe fallback.
- vision/agent.py: _invoke_local_vlm() guards resp.content or "" and returns None on empty output.
- multimodal/vlm_adapter.py: Same guard applied.
- orchestration/understanding.py: Raises clean TaskUnderstandingError on empty content with actionable message.

---

## 16. Tests

| Test File | Coverage |
|---|---|
| tests/test_vision_schemas.py | Schema validation, confidence tier computation |
| tests/test_dimension_extractor.py | Regex extraction, tolerance parsing, ambiguity handling, Section 9 value=None rule |
| tests/test_industrial_inspector.py | Candidate language enforcement, sanitize_engineering_language() |
| tests/test_image_preprocessing.py | EXIF correction, contrast equalization, tile generation, TileGenerationError |
| tests/test_region_detector.py | Heuristic region classification for title blocks, dimension regions, drawing body |
| tests/test_visual_verifier.py | All 6 deterministic verification checks, bounding box validation |
| tests/test_vision_agent.py | End-to-end process_image() and process_pdf_drawing() pipeline |
| tests/test_vision_tools.py | Tool contract registration and capability mapping |
| tests/test_vision_langgraph_integration.py | LangGraph routing to vision_agent and result propagation |
| tests/acceptance/test_phase_7_acceptance.py | Full Phase 7 acceptance criteria (21 checks + SIH demo target) |

Unit test result: 204 passed, 0 failed (Phases 0-7 regression suite).

---

## 17. Phase 5 Policy Invariants Preserved

- The vision_agent CANNOT override risk scores.
- The vision_agent CANNOT approve itself for privileged operations.
- High-risk plans involving confidential assets trigger REQUIRE_APPROVAL through PolicyEngine.
- Vision tool registrations are requires_approval=False only for standard non-privileged image reading.

---

## 18. Known Limitations

1. VLM Context Window: Very large drawings require tile-by-tile analysis; cross-tile spatial relationships are not automatically correlated.
2. Symbol Library: CAD symbol libraries (GD&T, weld symbols, P&ID) are not yet semantically decoded; flagged as SYMBOL type evidence only.
3. Persistent Evidence Store: Phase 7 evidence is held in-memory within the task result; cross-task retrieval via vector search is reserved for Phase 8 (RAG).
4. PDF Multi-Page: process_pdf_drawing() currently analyzes one page at a time; multi-page drawing set correlation is a Phase 8 enhancement.
