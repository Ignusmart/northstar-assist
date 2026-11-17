# Task 4: IAM facts (before/after policies)

Applied 2026-11-17.
- `before/`: the console-created default policies, exported as JSON.
- `after/`: the scoped inline policies (Access Analyzer `validate-policy`: **0 findings**).
- **Restore:** `aws iam attach-role-policy --role-name <role> --policy-arn arn:aws:iam::219317121475:policy/service-role/<name>`. The detached policies still exist.

## Harness execution role `AmazonBedrockAgentCoreHarnessDefaultServiceRole-68dqb`

**Before:** managed `AmazonBedrockAgentCoreHarnessExecutionPolicy_5zgdw` + `…HarnessGatewayPolicy_9ehrf`, 21 statements.
**After:** inline `NorthstarScopedHarnessExecution`, 6 statements.

| Original statement | Problem | After |
|---|---|---|
| `BedrockModelInvocation`: InvokeModel* on `foundation-model/*` (all Regions) **and** `arn:aws:bedrock:us-east-1:<acct>:*` | Any model, plus every Bedrock resource in the account. A per-request model override can run any model. | `InvokeApprovedModelOnly`: the **Nova 2 Lite US profile** + the foundation model in **us-east-1/us-east-2/us-west-2** (the Regions the profile routes to) |
| `BedrockMantleInference` / `BedrockMantleCallWithBearerToken` (`*`) | A second inference path, not used | **Removed** |
| `AgentCoreBrowserDefault` (7 actions) | Browser tool not configured | **Removed** |
| `AgentCoreCodeInterpreterDefault` (5 actions) | Code Interpreter not configured | **Removed** |
| `EFSClientAccess` / `EFSDescribe` (any file system) | No file system mounts configured | **Removed** |
| `S3FilesClientAccess` / `S3FilesDescribe` (incl. `ClientRootAccess`) | No S3 Files mounts; root access to any S3 file system | **Removed** |
| `AgentCoreMemory` (Create/Delete/Get/List events, RetrieveMemoryRecords) | Memory disabled | **Removed** |
| `CloudWatchMetricsPublish` (`PutMetricData` on `*`) | Not needed (the harness answered without it) | **Removed** |
| `CloudWatchLogsDescribeGroups` on `log-group:*` | Can enumerate every log group | **Removed** |
| `CloudWatchLogsGroup/Stream` on `runtimes/*` | Could write to **any** runtime's logs (log tampering) | `OwnRuntimeLogsOnly`: just `harness_NorthstarAssist-2X0VnqAgmt-DEFAULT` (+ its streams) |
| `CloudWatchLogsPutResourcePolicy` | Not needed | **Removed** |
| `AgentCoreWorkloadIdentity` on `harness_NorthstarAssist-*` | Wildcard name | `OwnWorkloadIdentityOnly`: the exact `harness_NorthstarAssist-2X0VnqAgmt` |
| `AgentCoreGatewayAccess`: InvokeGateway on the one gateway | Already scoped | Kept (`InvokeNorthstarGatewayOnly`) |
| ECR pull on `repository/harness-*` | AWS-owned harness image repo, account unknown | Kept (`PullHarnessRuntimeImage`) |

**Remaining `*`, each justified (the rubric requires this):**
- `ecr:GetAuthorizationToken`, `ecr-public:GetAuthorizationToken`, `sts:GetServiceBearerToken`, `xray:PutTraceSegments`, `xray:PutTelemetryRecords`: these actions **don't support resource-level permissions**, so IAM only accepts `*`. They grant tokens and telemetry writes, not data access.
- `repository/harness-*` with account `*`: the runtime image lives in an AWS-owned account.
- `log-stream:*`: stream names are generated per session, but it's limited to one log group.
- (Task 5 adds the guardrail **Deny** on `Resource: "*"`. A Deny on everything is the safe direction.)

## Gateway service role `AmazonBedrockAgentCoreGatewayDefaultServiceRole1794928507558`

**Before:** `GatewayBasePolicyProd_78A0C4` + `GatewayKBAccessProd_81E1C6`, 9 statements.
**After:** inline `NorthstarScopedGateway`, 3 statements.

| Original | Problem | After |
|---|---|---|
| GetGateway on `northstar-assist-gateway-*` | Wildcard suffix | The exact gateway ARN |
| GetConfigurationBundleVersion on `configuration-bundle/*` (same account + Region condition) | Bundle IDs not known in advance | Kept, with the conditions |
| GetKnowledgeBase + Retrieve on KB `5CO8QOAYFZ` | Already scoped | Kept |
| `AgenticRetrieveStream` on `*` | Not used (Standard retrieval) | **Removed** |
| InvokeModel* on all foundation models, inference profiles, provisioned and custom models (CalledVia bedrock) | Model access the gateway doesn't need | **Removed** |
| `Rerank` on `*`, `GetInferenceProfile` on `inference-profile/*` | Not used | **Removed** |
| `ApplyGuardrail` on `guardrail/*` | Any guardrail; not used by the gateway | **Removed** |

## KB service role `AmazonBedrockExecutionRoleForKnowledgeBase_esapf` (left as is)
- Already scoped: `s3:ListBucket` on the bucket + `s3:GetObject` on `bucket/*` (with an account condition), and InvokeModel on **Titan Embed v2 only**.
- Minor extras: `cloudwatch:PutMetricData` (namespace-limited), `aws-marketplace:*Subscribe*` (CalledViaLast bedrock).

## Re-test after the swap (70 s propagation)

| Test | Result |
|---|---|
| KB question (hybrid work) | ✅ Retrieve + answer from the handbook. The request path still works. |
| **Model override** to `global.amazon.nova-2-lite-v1:0` (not on the allow-list) | ✅ **AccessDeniedException** on `bedrock:InvokeModelWithResponseStream`. The allow-list holds, even though the override is a caller-side choice. |

## Blast radius
- **Before:** a stolen harness role could:
  - invoke any model in any Region,
  - touch every Bedrock resource in the account (guardrails, KBs),
  - start Browser and Code Interpreter sessions,
  - mount any EFS or S3 Files system with root,
  - read and write AgentCore Memory,
  - write into other runtimes' logs.
  - The gateway role could call any model, Rerank, and apply any guardrail.
- **After:** the harness role can only:
  - call Nova 2 Lite,
  - call the one gateway,
  - write its own log group.
  - The gateway role can only read the one KB.
