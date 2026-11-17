# Northstar Assist: Build and Secure an AWS Bedrock RAG AI Agent

Udacity AI Security Engineer Nanodegree, Course 1 project, by **Jobelo Andrés Quintero Rodríguez**.

Northstar Assist is an internal employee assistant. It runs as an Amazon Bedrock AgentCore harness (Amazon Nova 2 Lite) that retrieves from a Bedrock Managed Knowledge Base (30 company documents in S3, Titan Text Embeddings V2) through an AgentCore gateway. The project builds the agent, threat-models it, and secures it with scoped IAM, Bedrock Guardrails, monitoring, and red-team testing.

**Launch recommendation: APPROVE WITH CONDITIONS** (see `deliverables/07_launch_readiness_report.md`).

## Deliverables

| Task | Deliverable | File(s) |
|---|---|---|
| 1 | Working harness with retrieval | `evidence/task1-harness.png`, `evidence/task1-retrieve.png`, `evidence/task1-transcript.md`, `evidence/task1-kb-sync.txt` |
| 2 | ML Bill of Materials | `deliverables/02_ML-BOM_Northstar_Assist.docx` |
| 3 | STRIDE-ML threat model | `deliverables/03_STRIDE-ML_Northstar_Assist.docx` |
| 4 | IAM hardening summary | `deliverables/04_iam_hardening_summary.md`, policies in `iam/before/` and `iam/after/`, `evidence/task4-override-tests.txt` |
| 5 | Safety and response controls | `deliverables/05_safety_controls.md`, `guardrail/` |
| 6 | Monitoring plan and incident response playbook | `deliverables/06_monitoring_and_ir_playbook.md`, `monitoring/`, `evidence/task6-alarm-trigger.txt`, `evidence/task6-monitoring-checks.txt` |
| 7 | Edge-case testing and launch-readiness report | `deliverables/07_launch_readiness_report.md`, `evidence/task7-*.txt`, `redteam/` |

## Key results

- Knowledge base sync: 30 documents scanned, 30 indexed, 0 failed.
- IAM: harness role reduced from 22 statements to 6; an IAM Deny blocks any model call made without the guardrail.
- Guardrail v1 (Classic tier): prompt attack, content filters, 2 denied topics, PII masking/blocking. All 17 direct-injection attempts were blocked; sensitive-data prompts were blocked (business financials, secrets) or masked (emails, phone numbers). Bulk enumeration of names and titles is still possible (finding F2).
- Monitoring: 3 CloudWatch alarms and 2 metric filters; the guardrail-interventions alarm fired during testing.
- Remaining risk: indirect prompt injection through knowledge-base documents (2 of 3 poisoned-document tests succeeded), because guardrails don't screen retrieved chunks.

## Layout

```
deliverables/  Task 2-7 documents
evidence/      transcripts, screenshots and test logs
iam/           original (before/) and scoped (after/) IAM policies
guardrail/     guardrail configuration and harness model config
monitoring/    CloudWatch alarms and metric filters
redteam/       the poisoned document used for the indirect-injection test (removed from S3 afterwards)
ns_test.py     test runner that invokes the harness and prints tool calls and answers
```

No credentials are stored in this repository. The AWS account was a temporary Udacity lab account.
