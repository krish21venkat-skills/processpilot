"""Stage 0 smoke test: checks embeddings and the LLM through Bedrock."""
import json
import os

import boto3
from dotenv import load_dotenv

load_dotenv()
session = boto3.Session(
    profile_name=os.environ["AWS_PROFILE"],
    region_name=os.environ["AWS_REGION"],
)
client = session.client("bedrock-runtime")


def test_embedding() -> None:
    resp = client.invoke_model(
        modelId=os.environ["EMBED_MODEL_ID"],
        body=json.dumps({"inputText": "invoice approval limit"}),
    )
    vec = json.loads(resp["body"].read())["embedding"]
    print("Embedding length:", len(vec))


def test_llm() -> None:
    resp = client.converse(
        modelId=os.environ["LLM_MODEL_ID"],
        messages=[{"role": "user", "content": [{"text": "Reply with the word OK."}]}],
        inferenceConfig={"maxTokens": 20},
    )
    print("LLM reply:", resp["output"]["message"]["content"][0]["text"])


if __name__ == "__main__":
    test_embedding()
    test_llm()