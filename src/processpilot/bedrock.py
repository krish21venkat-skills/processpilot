"""Thin Bedrock wrapper: embeddings now, LLM calls in later stages."""
import json
from functools import lru_cache

import boto3

from processpilot import config


@lru_cache(maxsize=1)
def client():
    session = boto3.Session(profile_name=config.AWS_PROFILE, region_name=config.AWS_REGION)
    return session.client("bedrock-runtime")


def embed(text: str) -> list[float]:
    resp = client().invoke_model(
        modelId=config.EMBED_MODEL_ID,
        body=json.dumps({"inputText": text, "dimensions": 1024, "normalize": True}),
    )
    return json.loads(resp["body"].read())["embedding"]

USAGE = {"in": 0, "out": 0}  # running token totals for cost reporting


def chat(system: str, user: str, max_tokens: int = 400) -> str:
    resp = client().converse(
        modelId=config.LLM_MODEL_ID,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.0},
    )
    USAGE["in"] += resp["usage"]["inputTokens"]
    USAGE["out"] += resp["usage"]["outputTokens"]
    return resp["output"]["message"]["content"][0]["text"]