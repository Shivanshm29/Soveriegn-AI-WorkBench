# Artifact Factory

## Principle

The workbench produces real deliverables, not just chat responses.

## Supported initial artifacts

- DOCX
- XLSX
- CSV
- PDF/report
- source code
- ZIP/code bundle

## Artifact pipeline

```text
Agent result
 ↓
Artifact generation
 ↓
File existence check
 ↓
Structural validation
 ↓
Content validation
 ↓
Provenance attachment
 ↓
Artifact store
 ↓
Delivery
```

## DOCX verification

Check:
- file opens
- expected headings exist
- required evidence is present
- no empty document
- source references exist

## XLSX verification

Check:
- workbook opens
- required sheets exist
- required cells contain values/formulas
- formulas are not broken
- output can be reopened

## Code artifact verification

Check:
- files exist
- syntax check
- tests execute
- sandbox result attached

## Artifact manifest

```json
{
  "artifact_id": "art_001",
  "task_id": "task_001",
  "type": "docx",
  "filename": "approval_note.docx",
  "sha256": "...",
  "created_by_agent": "document_agent",
  "verified": true,
  "verification": {}
}
```
