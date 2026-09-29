"""Deterministic verification of code execution outputs, limits, and isolation."""

import os
import hashlib
import json
import re
from typing import Dict, List, Optional, Any
from backend.app.sandbox.schemas import (
    CodeExecutionRequest,
    CodeExecutionResult,
    VerificationStatus,
)


class CodeExecutionVerifier:
    """Performs strict deterministic verification on sandbox execution results."""

    @staticmethod
    def verify(
        request: CodeExecutionRequest,
        result: CodeExecutionResult,
        workspace_path: Optional[str] = None,
    ) -> VerificationStatus:
        """Verify code execution results against contracts, expectations, and safety bounds."""
        checks: Dict[str, bool] = {}
        failure_reasons: List[str] = []
        details: Dict[str, Any] = {}

        # 1. Exit code verification
        exit_code_zero = (result.exit_code == 0)
        checks["exit_code_zero"] = exit_code_zero
        if not exit_code_zero:
            failure_reasons.append(f"Process exited with non-zero returncode: {result.exit_code}")

        # 2. Status verification
        status_ok = (result.status == "SUCCESS")
        checks["status_success"] = status_ok
        if not status_ok:
            failure_reasons.append(f"Execution status was {result.status}, not SUCCESS")

        # 3. Network isolation verification (must remain strictly blocked)
        checks["network_isolated"] = bool(result.network_blocked)
        if not result.network_blocked:
            failure_reasons.append("Network isolation violation detected: network was not blocked.")

        # 4. Resource limit verification
        within_timeout = (result.status != "TIMEOUT")
        checks["within_timeout"] = within_timeout
        if not within_timeout:
            failure_reasons.append(f"Execution exceeded timeout limit ({request.config.timeout_seconds}s)")

        within_output_limit = len(result.stdout) + len(result.stderr) <= request.config.max_output_bytes
        checks["within_output_limit"] = within_output_limit
        if not within_output_limit:
            failure_reasons.append("Output exceeded maximum byte limit")

        # 5. Expected output patterns
        if request.expected_output_patterns:
            all_patterns_found = True
            missing_patterns = []
            for pat in request.expected_output_patterns:
                if not re.search(pat, result.stdout):
                    all_patterns_found = False
                    missing_patterns.append(pat)
            checks["expected_output_patterns"] = all_patterns_found
            if not all_patterns_found:
                failure_reasons.append(f"Missing expected output pattern(s): {missing_patterns}")

        # 6. Expected files created in workspace
        if request.expected_files and workspace_path and os.path.exists(workspace_path):
            missing_files = []
            file_hashes = {}
            for rel_file in request.expected_files:
                target_path = os.path.normpath(os.path.join(workspace_path, rel_file))
                # Ensure within workspace
                if not target_path.startswith(os.path.normpath(workspace_path)):
                    missing_files.append(rel_file)
                    continue
                if not (os.path.exists(target_path) and os.path.isfile(target_path)):
                    missing_files.append(rel_file)
                else:
                    with open(target_path, "rb") as f:
                        file_hashes[rel_file] = hashlib.sha256(f.read()).hexdigest()

            files_created_ok = (len(missing_files) == 0)
            checks["expected_files_exist"] = files_created_ok
            details["file_hashes"] = file_hashes
            if not files_created_ok:
                failure_reasons.append(f"Expected file(s) not created: {missing_files}")

        is_verified = (len(failure_reasons) == 0) and all(checks.values())
        return VerificationStatus(
            is_verified=is_verified,
            checks=checks,
            failure_reasons=failure_reasons,
            details=details,
        )
