"""Northstar Assist test runner: one new session per prompt, prints tools, stop reasons, answer.

    AWS_PROFILE=udacity-ai-security-engineer python ns_test.py "prompt" ...
    OVERRIDE=global.amazon.nova-2-lite-v1:0 python ...ns_test.py "prompt"   # per-request model override, no guardrailConfig
"""
import os
import sys
import uuid

import boto3
from botocore.config import Config

HARNESS = "arn:aws:bedrock-agentcore:us-east-1:219317121475:harness/NorthstarAssist-dDBp3qRpDd"
client = boto3.client("bedrock-agentcore", region_name="us-east-1",
                      config=Config(read_timeout=120, retries={"total_max_attempts": 1}))
extra = {}
if os.environ.get("OVERRIDE"):
    extra["model"] = {"bedrockModelConfig": {"modelId": os.environ["OVERRIDE"], "apiFormat": "converse_stream"}}

for prompt in sys.argv[1:]:
    sid = str(uuid.uuid4())
    answer, tools, stops = "", [], []
    try:
        resp = client.invoke_harness(harnessArn=HARNESS, runtimeSessionId=sid,
                                     messages=[{"role": "user", "content": [{"text": prompt}]}], **extra)
        for e in resp["stream"]:
            if "contentBlockDelta" in e:
                answer += e["contentBlockDelta"]["delta"].get("text", "")
            elif "contentBlockStart" in e and "toolUse" in e["contentBlockStart"].get("start", {}):
                tools.append(e["contentBlockStart"]["start"]["toolUse"]["name"])
            elif "messageStop" in e:
                stops.append(e["messageStop"].get("stopReason"))
            elif any(k.endswith(("Exception", "Error")) for k in e):
                answer += f"\n[STREAM ERROR] {e}"
    except Exception as exc:
        answer = f"[ERROR] {exc}"
    print(f"> {prompt}\n  session={sid} tools={tools} stops={stops}\n{answer}\n{'-' * 60}")
