# Code Execution Sandbox

## Goal

Allow the coding/data agents to execute code while containing it.

## Default sandbox properties

```text
network: none
read host filesystem: no
write host filesystem: no
CPU limit: configured
RAM limit: configured
process limit: configured
execution timeout: configured
output limit: configured
temporary workspace: yes
cleanup after run: yes
```

## Execution result

```json
{
  "execution_id": "exec_123",
  "exit_code": 1,
  "stdout": "...",
  "stderr": "...",
  "duration_ms": 823,
  "files_created": [],
  "timed_out": false,
  "network_allowed": false
}
```

## Agent loop

```text
generate
 ↓
execute
 ↓
observe
 ├── success → verify
 └── failure → diagnose
                ↓
              repair
                ↓
              execute
```

## Verification

Code is not considered successful because the model says it works.

Success requires:
- process completed
- exit code acceptable
- required tests passed
- expected output exists
- no policy violation

## Sandbox escape tests

Acceptance tests must attempt:
- outbound HTTP
- reading host paths
- writing outside workspace
- process explosion
- timeout
- oversized output

All must be contained according to policy.
