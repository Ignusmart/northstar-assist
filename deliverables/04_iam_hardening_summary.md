# Northstar Assist: IAM Hardening Summary

**System:** Northstar Assist. An Amazon Bedrock AgentCore harness (`NorthstarAssist`, model Amazon Nova 2 Lite) retrieves from a Managed Knowledge Base (`northstar-assist-kb`) through an AgentCore Gateway (`northstar-assist-gateway`).
**Account / Region:** 219317121475 / us-east-1
**Date:** 17 November 2026

## 1. Purpose and method

The console created a default service role for each AgentCore component. Those roles are written to work for any harness configuration, so they grant far more than Northstar Assist uses. I reviewed each role against the actual request path and kept only the permissions that path needs:

```
Employee → harness (execution role) → model: Nova 2 Lite
                                  └─→ gateway (gateway service role) → knowledge base: Retrieve
Knowledge base sync (KB service role) → S3 bucket (read) + Titan Text Embeddings V2
```

The method is the same for every role:
1. Trace what the role actually does.
2. Allow one action on one named resource for each step.
3. Remove everything else.

The fixed policies were checked with IAM Access Analyzer `validate-policy` (0 findings) and re-tested live before this summary was written.

## 2. Roles reviewed

| Role | Assumed by | Job on the request path | Action taken |
|---|---|---|---|
| `AmazonBedrockAgentCoreHarnessDefaultServiceRole-68dqb` | AgentCore harness | Calls the model and the gateway, writes its runtime logs | **Scoped** (main change) |
| `AmazonBedrockAgentCoreGatewayDefaultServiceRole1794928507558` | AgentCore Gateway | Retrieves from the knowledge base | **Scoped** |
| `AmazonBedrockExecutionRoleForKnowledgeBase_esapf` | Bedrock knowledge base, during a sync | Reads documents from S3 and creates embeddings | Reviewed, left as is (already scoped) |

## 3. Harness execution role (agent execution role)

**Original:**
- Two AWS-generated managed policies, `AmazonBedrockAgentCoreHarnessExecutionPolicy_5zgdw` and `AmazonBedrockAgentCoreHarnessGatewayPolicy_9ehrf`, with **21 statements** in total.

**Scoped:**
- One inline policy, `NorthstarScopedHarnessExecution`, with **6 statements**.
- In Task 5, two guardrail statements were added (section 3.3).
- The original managed policies were detached, not deleted, so they can be re-attached if a rollback is needed.

### 3.1 Before vs after

| # | Original permission | Problem | Change | Rationale |
|---|---|---|---|---|
| 1 | `bedrock:InvokeModel`, `InvokeModelWithResponseStream` on `arn:aws:bedrock:*::foundation-model/*` **and** `arn:aws:bedrock:us-east-1:219317121475:*` | Any foundation model in any Region, plus every Bedrock resource in the account | Limited to the **Nova 2 Lite US inference profile** and the **Nova 2 Lite foundation model in us-east-1, us-east-2 and us-west-2** | `InvokeHarness` accepts a per-request `model` override and has no condition keys, so the caller's policy can't restrict it. **Only this role decides which models an override can reach.** The profile routes across three Regions, so all three foundation model ARNs are required. |
| 2 | `bedrock-mantle:CreateInference`, `bedrock-mantle:CallWithBearerToken` (the second on `*`) | A second inference path that Northstar Assist doesn't use | **Removed** | Unused access is pure exposure. |
| 3 | AgentCore **Browser** (7 actions on `browser/*`) | The Browser tool isn't configured | **Removed** | A compromised role could browse the web on the company's behalf, which is a data exfiltration path. |
| 4 | AgentCore **Code Interpreter** (5 actions on `code-interpreter/*`) | Code Interpreter isn't configured | **Removed** | It would allow running arbitrary code inside AWS under this identity. |
| 5 | **EFS** `ClientMount` / `ClientWrite` / `Describe*` on every file system in the account | No file system mounts are configured | **Removed** | It would allow reading and writing any EFS file system in the account. |
| 6 | **S3 Files** `ClientMount` / `ClientWrite` / **`ClientRootAccess`** on every S3 file system | No S3 Files mounts are configured | **Removed** | Root-level write access to any S3 file system is a high-impact grant with no business need. |
| 7 | AgentCore **Memory** (Create/Delete/Get/List events, RetrieveMemoryRecords) | Memory is disabled on the harness | **Removed** | It would allow reading or deleting other conversations' memory if Memory were ever enabled. |
| 8 | `logs:CreateLogGroup`, `DescribeLogStreams`, `CreateLogStream`, `PutLogEvents` on `/aws/bedrock-agentcore/runtimes/*` | It could write into **any** AgentCore runtime's logs | Limited to the harness's own log group `/aws/bedrock-agentcore/runtimes/harness_NorthstarAssist-2X0VnqAgmt-DEFAULT` and its streams | An attacker could otherwise forge or pollute other runtimes' logs and hide activity. |
| 9 | `logs:DescribeLogGroups` on `log-group:*` | It could enumerate every log group in the account | **Removed** | That's reconnaissance value with no runtime need. |
| 10 | `logs:PutResourcePolicy` | It could change log resource policies | **Removed** | It isn't needed to write logs. |
| 11 | `cloudwatch:PutMetricData` on `*` (namespace `bedrock-agentcore`) | Not needed for the harness to answer | **Removed** | The re-test passed without it, and metric injection could distort monitoring. |
| 12 | `bedrock-agentcore:GetWorkloadAccessToken*` on `workload-identity/harness_NorthstarAssist-*` | Wildcard name suffix | Limited to the exact identity `harness_NorthstarAssist-2X0VnqAgmt` | A name wildcard could match a different harness with a similar name. |
| 13 | `bedrock-agentcore:InvokeGateway` on the Northstar gateway | Already scoped to one gateway | **Kept** | It's the harness's only route to the knowledge base. |
| 14 | ECR image pull on `arn:aws:ecr:us-east-1:*:repository/harness-*` | — | **Kept** | The harness runtime image lives in an AWS-owned repository. |
| 15 | `ecr:GetAuthorizationToken`, `ecr-public:GetAuthorizationToken`, `sts:GetServiceBearerToken`, `xray:PutTraceSegments`, `xray:PutTelemetryRecords`, `xray:GetSampling*` | — | **Kept**, except `xray:GetSampling*`, which was removed | The runtime needs these to start and send traces (see section 3.2). |

### 3.2 Remaining wildcards, each justified

| Wildcard | Why it remains |
|---|---|
| `Resource: "*"` on `ecr:GetAuthorizationToken`, `ecr-public:GetAuthorizationToken`, `sts:GetServiceBearerToken`, `xray:PutTraceSegments`, `xray:PutTelemetryRecords` | **These actions don't support resource-level permissions**, so IAM accepts only `*`. They issue registry or service tokens and write telemetry. **They grant no access to data, models or other resources.** |
| Account `*` in `arn:aws:ecr:us-east-1:*:repository/harness-*` | The harness runtime image is in an **AWS-owned account** whose ID isn't published. It's limited to `harness-*` repositories and read-only image pull actions. |
| `:log-stream:*` on the harness log group | Log stream names are generated per session. It's limited to **one** log group. |
| `Resource: "*"` on the **Deny** statement (section 3.3) | It's a **Deny**, so `*` makes it stricter, not broader: any model call without the Northstar guardrail is refused. |

No action wildcards (`service:*`) remain in the harness role.

### 3.3 Guardrail statements (added in Task 5, inline policy `NorthstarGuardrailEnforcement`)

| Statement | Effect |
|---|---|
| `ApplyNorthstarGuardrail`: `bedrock:ApplyGuardrail` on `arn:aws:bedrock:us-east-1:219317121475:guardrail/7x0s89htsojp` only | Lets the harness apply **its own** guardrail. The default role didn't include this, and without it every request fails. |
| `DenyModelCallsWithoutNorthstarGuardrail`: **Deny** `bedrock:InvokeModel*` on `*` when `bedrock:GuardrailIdentifier` is not the Northstar guardrail ARN (`ArnNotLike`, ARN and `ARN:*`) | **Makes the guardrail mandatory at the IAM layer.** A per-request model override that leaves out the guardrail, or names a weaker one, is denied. |

## 4. Gateway service role

**Original:**
- Two managed policies, `AmazonBedrockAgentCoreGatewayBasePolicyProd_78A0C4` and `AmazonBedrockAgentCoreGatewayKBAccessProd_81E1C6`, with **9 statements**.

**Scoped:**
- One inline policy, `NorthstarScopedGateway`, with **3 statements**.

| Original permission | Problem | Change | Rationale |
|---|---|---|---|
| `bedrock-agentcore:GetGateway` on `gateway/northstar-assist-gateway-*` | Wildcard suffix | The exact gateway ARN | The gateway only needs to read itself. |
| `GetConfigurationBundleVersion` on `configuration-bundle/*` (same-account and same-Region conditions) | Bundle IDs aren't known in advance | **Kept, with its conditions** | Required by the gateway service. The conditions keep it to this account and Region. |
| `bedrock:GetKnowledgeBase`, `bedrock:Retrieve` on `knowledge-base/5CO8QOAYFZ` | Already scoped | **Kept** | It's the gateway's one job. |
| `bedrock:AgenticRetrieveStream` on `*` | The target uses Standard retrieval | **Removed** | Unused, and it was on every resource. |
| `bedrock:InvokeModel*` on all foundation models, inference profiles, provisioned and custom models | The gateway doesn't call models for Standard retrieval | **Removed** | It's a second, unrestricted path to every model. |
| `bedrock:Rerank` on `*`, `bedrock:GetInferenceProfile` on `inference-profile/*` | Not used | **Removed** | Unused. |
| `bedrock:ApplyGuardrail` on `guardrail/*` | Any guardrail in the account; the gateway doesn't apply one | **Removed** | Guardrails are applied by the harness. |

## 5. Knowledge base service role (reviewed, not changed)

The KB service role was already scoped:
- `s3:ListBucket` on `northstar-assist-kb-jaqr-101020`.
- `s3:GetObject` on `northstar-assist-kb-jaqr-101020/*`. Both are limited to this account by an `aws:ResourceAccount` condition.
- `bedrock:InvokeModel` on **Titan Text Embeddings V2 only**.

It has **no** `PutObject` or `DeleteObject`, so a compromised sync role can't plant or delete documents (knowledge base poisoning). Its remaining extras are minor and conditioned:
- `cloudwatch:PutMetricData`, limited to the `AWS/Bedrock/KnowledgeBases` namespace.
- `aws-marketplace` subscription actions, only when called through Bedrock.

These were left in place to avoid breaking the sync.

## 6. Verification

The policies were applied, and the test ran after a 70-second IAM propagation wait.

| Test | Expected | Observed |
|---|---|---|
| Knowledge base question ("What is Northstar's hybrid work policy?") | Retrieve tool call + grounded answer | ✅ `northstar-kb___Retrieve` called. The answer came from `company_policies_handbook.html`. **The request path still works.** |
| Per-request model override to `global.amazon.nova-2-lite-v1:0` (not on the allow-list) | Denied | ✅ `AccessDeniedException`: the harness role is not authorized to perform `bedrock:InvokeModelWithResponseStream` on that model. **The model allow-list holds.** |
| Per-request override to the **approved** model `us.amazon.nova-2-lite-v1:0` **without** `guardrailConfig` (after Task 5) | Denied by the guardrail Deny | ✅ `AccessDeniedException` on `bedrock:InvokeModelWithResponseStream`. The model is allowed, so the denial comes from **the guardrail requirement**. |
| `aws accessanalyzer validate-policy` on both scoped policies and `NorthstarGuardrailEnforcement` | No errors or security warnings | ✅ 0 findings |

## 7. Blast radius: before vs after

**Before:** an attacker who obtained the harness role's credentials could:
- invoke any foundation model in any Region,
- act on every Bedrock resource in the account, including guardrails and knowledge bases,
- start Browser and Code Interpreter sessions,
- mount any EFS or S3 Files system with root write access,
- read and delete AgentCore Memory,
- and write into every AgentCore runtime's logs to cover their tracks.

With the gateway role, they could also call any model, run Rerank, and apply any guardrail.

**After:** the same stolen harness credentials can only:
- call **Nova 2 Lite**, **with the Northstar guardrail applied**,
- invoke **the one Northstar gateway**,
- and write to **the harness's own log group**.

The gateway role can only read and retrieve from **the one Northstar knowledge base**. An attacker can no longer change configuration, switch models, reach other data stores, or tamper with other logs. The worst case shrinks from "the whole Bedrock and AgentCore account" to "ask Northstar Assist questions through its guardrail."
