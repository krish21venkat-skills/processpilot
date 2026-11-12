"""Central settings, loaded from .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

AWS_PROFILE = os.environ["AWS_PROFILE"]
AWS_REGION = os.environ["AWS_REGION"]
EMBED_MODEL_ID = os.environ["EMBED_MODEL_ID"]
LLM_MODEL_ID = os.environ["LLM_MODEL_ID"]

POLICY_DIR = ROOT / "data" / "policies"
CHROMA_DIR = ROOT / ".chroma"
COLLECTION = "policies"

UIPATH_ORG = os.getenv("UIPATH_ORG", "")
UIPATH_TENANT = os.getenv("UIPATH_TENANT", "")
UIPATH_FOLDER = os.getenv("UIPATH_FOLDER", "Shared/ProcessPilot")
UIPATH_QUEUE = os.getenv("UIPATH_QUEUE", "ProcessPilotInvoices")
UIPATH_CLIENT_ID = os.getenv("UIPATH_CLIENT_ID", "")
UIPATH_CLIENT_SECRET = os.getenv("UIPATH_CLIENT_SECRET", "")
UIPATH_SCOPES = os.getenv("UIPATH_SCOPES", "")