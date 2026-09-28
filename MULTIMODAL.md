# Multimodal Pipeline

## Principle

A scanned document is not just text.

The pipeline preserves:
- text
- layout
- tables
- images
- coordinates
- page numbers
- OCR confidence
- visual observations

## Pipeline

```text
Input
 ↓
File type detection
 ↓
PDF/document parser
 ↓
Page rendering if needed
 ↓
OCR
 ↓
Layout/table extraction
 ↓
Vision-language reasoning
 ↓
Normalized Evidence Objects
```

## Evidence object

```json
{
  "evidence_id": "ev_001",
  "document_id": "doc_123",
  "page": 7,
  "type": "visual_observation",
  "text": "...",
  "bbox": [120, 340, 600, 510],
  "ocr_confidence": 0.94,
  "model_id": "...",
  "source_hash": "...",
  "created_at": "..."
}
```

## OCR strategy

Use PaddleOCR locally for deterministic text extraction and coordinates.

Use the VLM for:
- ambiguous visual text
- layout interpretation
- diagrams
- relationships
- image-level reasoning

Do not make the VLM the only OCR mechanism.

## Engineering drawing policy

The system produces:

```text
OBSERVATION
EVIDENCE REGION
CONFIDENCE
```

It must not label an AI observation as an engineering certification.

## Handwritten notes

Treat handwriting as:
- OCR candidate
- visual interpretation
- confidence-scored evidence

Low-confidence handwriting must be marked for review.

## Multimodal model selection

The router must choose a vision-capable model when image input materially affects the task.

A text-only model may summarize already-extracted text, but it must not be presented as having visually inspected the source image.
