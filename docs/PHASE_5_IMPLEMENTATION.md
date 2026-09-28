# Phase 5 Implementation Report — Risk / Policy / Human Approval

## Executive Summary
Phase 5 of the Sovereign On-Premise Agentic AI Workbench implements the deterministic risk assessment, policy engine, data sensitivity classification, and human-in-the-loop approval lifecycle integrated with the LangGraph state machine.

This phase guarantees that model planning and task understanding cannot bypass security boundaries. Every plan proposed by the LLM is subjected to deterministic risk calculation, strict policy evaluation based on a local configuration file (`configs/policies.yaml`), and mandatory human authorization when required. In accordance with zero-egress sovereignty constraints (`SOVEREIGN_MODE=True`), external network calls and cloud fallback are non-bypassable hard denials that cannot be permitted even by human approvers.

---

## 1. Risk Model
The risk assessment system is deterministic, auditable, and decoupled from LLM opinions:
- **Location**: `backend/app/security/risk.py`
- **Risk Levels**: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- **Structured Model**: `RiskAssessment` containing:
  - `task_id`
  - `plan_id`
  - `risk_level`
  - `risk_score` (normalized `0.0` to `1.0`)
  - `risk_factors` (list of matching risk factors)
  - `affected_resources` (paths, resources, targets)
  - `affected_tools` (tools referenced across plan steps)
  - `affected_data` (sensitive datasets/domains involved)
  - `reasoning` (deterministic explanation of calculation)
  - `policy_version`
  - `timestamp`
- **Standard Risk Factors** (minimum 10 implemented):
  1. `sensitive_data_access`: Plan touches `CONFIDENTIAL` or `RESTRICTED` data.
  2. `external_network_access`: Plan references outbound connectivity or unverified remote endpoints.
  3. `file_write`: Plan mutates filesystem artifacts.
  4. `file_delete`: Plan attempts deletion of files.
  5. `code_execution`: Plan invokes runtime interpreters or sandbox execution.
  6. `spreadsheet_modification`: Plan modifies tabular/spreadsheet data.
  7. `document_generation`: Plan creates official reports or documents.
  8. `system_configuration`: Plan modifies host or platform configuration.
  9. `privileged_operation`: Plan requests administrative or elevated capabilities.
  10. `high_impact_output`: Plan produces high-consequence outputs.
- **Deterministic Risk Engine (`RiskEngine`)**:
  - Accumulates weighted scores from tool risk levels, agent capabilities, and data sensitivity.
  - Maps final score against configurable policy thresholds (`LOW` <= 0.25, `MEDIUM` <= 0.50, `HIGH` <= 0.75, `CRITICAL` > 0.75).
  - Flags mandatory critical factors (e.g. external network or file delete) to immediately elevate risk.

---

## 2. Data Sensitivity
Data classification is explicitly represented and decoupled from freeform LLM prompts:
- **Location**: `backend/app/security/data_sensitivity.py`
- **Tiers**:
  - `PUBLIC`: Openly publishable, non-sensitive information (score: 0.0).
  - `INTERNAL`: Organization-internal, non-public data (score: 0.2).
  - `CONFIDENTIAL`: Proprietary business/engineering data (score: 0.5). Elevates task risk to at least `MEDIUM`.
  - `RESTRICTED`: Highly classified, mission-critical data (score: 0.8). Elevates task risk to at least `HIGH` and mandates approval.
- **Fail-Closed Parsing**: `parse_data_sensitivity()` validates user/input sensitivity and defaults to `RESTRICTED` if an invalid or unknown tier is supplied.

---

## 3. Policy Engine
The policy engine enforces deterministic governance over proposed plans:
- **Location**: `backend/app/security/policy_engine.py`
- **Outcomes**: `ALLOW`, `REQUIRE_APPROVAL`, `DENY`.
- **Structured Decision**: `PolicyDecision` containing:
  - `decision`: Policy outcome (`ALLOW`, `REQUIRE_APPROVAL`, `DENY`)
  - `reason`: Explanation of the outcome
  - `risk_level`: Evaluated `RiskLevel`
  - `policy_version`: Policy configuration version string
  - `matched_rules`: List of matched rule names
  - `task_id`: Bound task identifier
  - `plan_id`: Bound execution plan identifier
  - `timestamp`: UTC ISO timestamp
- **Evaluation Order**:
  1. *Sovereignty Check*: Any plan requesting external network or cloud models is immediately `DENY`.
  2. *Security / Registry Validation (Fail Closed)*: Any unknown tool or unknown agent is immediately `DENY`.
  3. *Denied Operations*: Any operation matching `denied_operations` in policy config is `DENY`.
  4. *Sensitive Data Restrictions*: Restricted operations on confidential/restricted data.
  5. *Approval Requirements*: High risk, critical risk, restricted data, or high-risk tools trigger `REQUIRE_APPROVAL`.
  6. *Default Allow*: Operations with acceptable risk and valid registration evaluate to `ALLOW`.

---

## 4. Policy Configuration
Policy rules are loaded from a version-controlled YAML configuration file:
- **Location**: `configs/policies.yaml`
- **Features**:
  - `policy_version`: Explicit version tracking (e.g. `1.0.0`).
  - `sovereignty`: Zero-egress enforcement rules (`deny_external_network`, `deny_cloud_models`).
  - `risk_thresholds`: Numeric cutoffs for `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
  - `approval_requirements`: Rules triggering mandatory human approval (e.g. risk levels, data tiers, specific tools).
  - `denied_operations`: Unconditional denials (file deletion, arbitrary external execution).
  - `data_sensitivity_rules`: Requirements tied to `CONFIDENTIAL` and `RESTRICTED` classifications.
  - `tool_rules`: Risk scores and approval overrides for individual tools.

---

## 5. Tool Risk
Tool risk is resolved strictly through the Phase 3 `ToolRegistry`:
- Tools cannot be invented by the LLM. Every tool mentioned in plan steps is checked against `ToolRegistry`.
- Tool metadata informs risk evaluation:
  - `file_read`: `LOW` risk.
  - `file_write`: `MEDIUM` risk.
  - `python_calculation`: `MEDIUM` risk.
  - `sandbox_execute`: `HIGH` risk (mandates approval).
  - `external_network`: Hard `DENY` in sovereign mode.
- Unknown tools immediately trigger fail-closed `DENY` decisions.

---

## 6. Human Approval Model
Human approval objects provide an immutable, cryptographic authorization contract:
- **Location**: `backend/app/security/approval.py`
- **Approval Request (`ApprovalRequest`)**:
  - `approval_id`: Unique UUID.
  - `task_id`: Bound task ID.
  - `plan_id`: Bound plan ID.
  - `plan_hash`: SHA-256 hash of the execution plan steps and capabilities.
  - `requested_by`: Requester identifier.
  - `risk_level`: Associated risk level.
  - `action_summary`: Summary of requested action.
  - `affected_resources`: List of affected file paths/resources.
  - `affected_tools`: List of tools requested.
  - `reasons`: Policy reasons for requiring approval.
  - `policy_version`: Policy version evaluated.
  - `created_at`: Creation timestamp.
  - `expires_at`: Expiration timestamp (default: 3600 seconds).
  - `status`: `PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`, `CANCELLED`.
- **Approval Decision (`ApprovalDecision`)**:
  - `approval_id`: Target approval ID.
  - `decision`: `APPROVED` or `REJECTED`.
  - `approver`: Human operator identity.
  - `timestamp`: Decision timestamp.
  - `reason`: Human justification.
  - `authorization_scope`: Exact authorized scope string.

---

## 7. Approval Lifecycle
The approval lifecycle follows a strict state progression:
1. `PENDING`: Request created and waiting for human input. Execution is paused.
2. `APPROVED`: Approver grants permission for the specific plan hash and task ID.
3. `REJECTED`: Approver denies permission. Graph transitions task to `FAILED`.
4. `EXPIRED`: Current time exceeds `expires_at`. Approval cannot be used; re-approval is mandatory.
5. `CANCELLED`: Superseded or aborted approval request.
- **Approval Scope Binding & Immutability**:
  - The approval request records `plan_hash = compute_plan_hash(plan)`.
  - If the plan is modified (steps added, altered, or tools changed), the plan hash changes.
  - `ApprovalManager.verify_approval()` detects the mismatch and rejects the execution.

---

## 8. LangGraph Integration
The LangGraph state machine incorporates policy checks and conditional branching:
- **Workflow Topology**:
  ```
  UNDERSTAND -> ROUTE -> PLAN -> RISK_ASSESSMENT -> POLICY
                                                      |
                   +------------------+---------------+
                   |                  |               |
                 ALLOW        REQUIRE_APPROVAL      DENY
                   |                  |               |
                   v                  v               v
                EXECUTE        WAITING_APPROVAL     FAILED
                   |                  |               |
                   |             (HUMAN SUBMIT)       v
                   |                  |            DELIVER
                   |              APPROVED
                   |                  |
                   +<-----------------+
                   |
                   v
                OBSERVE -> VERIFY -> DELIVER
  ```
- **Conditional Routing (`route_after_policy`)**:
  - `ALLOW` -> proceeds directly to `execute`.
  - `REQUIRE_APPROVAL` -> emits `APPROVAL_REQUESTED`, sets task state to `WAITING_APPROVAL`, and pauses graph execution (routes to `deliver` as paused state).
  - `DENY` -> sets task state to `FAILED` and routes to `deliver`.
- **Pause and Resume (`submit_approval`)**:
  - `SovereignWorkbenchGraph.submit_approval(task_id, decision)` resumes the workflow with the approved decision.
  - Nodes `understand`, `route`, and `plan` detect existing state and run idempotently, preserving plan immutability.
  - `execute_node` executes only after verifying valid, non-expired, matching approval.

---

## 9. Fail-Closed Behavior
In adherence with mission-critical security guidelines, any ambiguity triggers immediate denial:
- **Unknown Tool**: Plan referencing unverified tools evaluates to `PolicyOutcome.DENY`.
- **Unknown Agent**: Plan referencing unregistered agent evaluates to `PolicyOutcome.DENY`.
- **Missing / Corrupted Policy File**: Falls back to internal strict policy that denies operations.
- **Invalid / Mismatched Approval**: Plan modification invalidates approval; execution fails closed.
- **Expired Approval**: Verification fails if `expires_at < current_time`.

---

## 10. Sovereignty Interaction
Phase 5 maintains absolute compliance with Phase 2 zero-egress architecture:
- Policy rules forbid any external internet connection (`external_network_access`).
- Prohibits cloud model fallbacks (`cloud_model_call`).
- Sovereign mode constraints take precedence over human approval. Even if a human attempts to approve an external network step, the policy engine and execution safety check enforce hard `DENY`.

---

## 11. Audit Events
All policy evaluations and approval transitions emit auditable lifecycle events:
- `RISK_ASSESSMENT_CREATED`: Emitted when risk scoring completes.
- `POLICY_EVALUATED`: Emitted after policy rule matching with outcome and matched rules.
- `APPROVAL_REQUESTED`: Emitted when transitioning to `WAITING_APPROVAL`.
- `APPROVAL_APPROVED`: Emitted when an operator grants approval.
- `APPROVAL_REJECTED`: Emitted when an operator rejects a request.
- `APPROVAL_EXPIRED`: Emitted when an approval request exceeds its TTL.

---

## 12. Policy Versioning
- Every `RiskAssessment`, `PolicyDecision`, and `ApprovalRequest` includes the active `policy_version` string (e.g. `1.0.0`).
- Updating `configs/policies.yaml` automatically stamps future decisions with the updated version without retroactively modifying historical records.

---

## 13. Test Results
Comprehensive test suite verifying all Phase 5 requirements:
- `tests/test_risk_assessment.py`: Test A (Risk levels & factors) — **PASS**
- `tests/test_data_sensitivity.py`: Test B (Data sensitivity tiers) — **PASS**
- `tests/test_policy_decision.py`: Test C (ALLOW, REQUIRE_APPROVAL, DENY) — **PASS**
- `tests/test_tool_risk.py`: Test D (Tool risk resolution from registry) — **PASS**
- `tests/test_unknown_tool_policy.py`: Test E (Unknown tool fail closed) — **PASS**
- `tests/test_unknown_agent_policy.py`: Test F (Unknown agent fail closed) — **PASS**
- `tests/test_approval_request.py`: Test G (Approval request generation) — **PASS**
- `tests/test_approval_pause.py`: Test H (Approval pause at WAITING_APPROVAL) — **PASS**
- `tests/test_approval_grant.py`: Test I (Approval grant and resume execution) — **PASS**
- `tests/test_approval_rejection.py`: Test J (Approval rejection terminal path) — **PASS**
- `tests/test_approval_expiration.py`: Test K (Approval expiration enforcement) — **PASS**
- `tests/test_approval_scope.py`: Test L (Approval plan hash invalidation) — **PASS**
- `tests/test_policy_sovereignty.py`: Test M (Sovereignty hard deny override) — **PASS**
- `tests/test_policy_version.py`: Test N (Policy version persistence) — **PASS**
- `tests/test_policy_audit_events.py`: Test O (Audit event recording) — **PASS**
- `tests/test_policy_fail_closed.py`: Test P (Comprehensive fail closed behavior) — **PASS**
- `tests/test_end_to_end_approval.py`: Complete human-in-the-loop workflow scenario — **PASS**
- `tests/acceptance/test_phase_5_acceptance.py`: Acceptance suite covering all criteria — **PASS**

**Full Regression Suite**: 242 passed, 1 skipped (0 failures) across Phases 0–5.

---

## 14. Known Limitations
1. **Interactive UI Approval Interface**: Approvals are currently submitted programmatically via `SovereignWorkbenchGraph.submit_approval()` or API. A web-based approval dashboard belongs to Phase 9.
2. **Sandbox Isolation**: While `sandbox_execute` is flagged as high-risk and policy-gated, full namespace containerization is scheduled for Phase 7.
3. **Multimodal OCR & Document Evidence**: Document extraction tools remain mock-ready placeholders until Phase 6.
