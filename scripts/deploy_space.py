"""Publish the Gradio runtime to a private Docker Space."""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import dotenv_values
from huggingface_hub import HfApi, get_token

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_PATTERNS = [
    "Dockerfile",
    "README.md",
    "app.py",
    "requirements.txt",
    "src/**/*.py",
    "data/samples/samples/*.mp3",
    "data/samples/samples/README.md",
    "docs/demo/echo-demo.mp4",
    "docs/demo/echo-demo-preview.png",
]
PROVIDER_KEYS = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "groq": "GROQ_API_KEY",
}


def runtime_files(root: Path = ROOT) -> list[str]:
    return sorted(
        {
            str(path.relative_to(root))
            for pattern in UPLOAD_PATTERNS
            for path in root.glob(pattern)
            if path.is_file()
        }
    )


def provider_settings(env_file: Path) -> tuple[str, str, str]:
    settings = dotenv_values(env_file)
    provider = settings.get("LLM_PROVIDER") or "openai"
    if provider not in PROVIDER_KEYS:
        raise ValueError("Select openai, gemini, or groq in LLM_PROVIDER.")
    key_name = PROVIDER_KEYS[provider]
    value = settings.get(key_name)
    if not value or not value.strip():
        raise ValueError(f"Configure {key_name} in the selected environment file.")
    return provider, key_name, value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", required=True, help="username/space-name")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument(
        "--check", action="store_true", help="Check authentication and package without publishing"
    )
    args = parser.parse_args()
    token = get_token()
    if not token:
        raise SystemExit("Authenticate with .venv/bin/hf auth login using a write-capable token.")
    api = HfApi(token=token)
    identity = api.whoami()
    role = identity.get("auth", {}).get("accessToken", {}).get("role")
    if role == "read":
        raise SystemExit("The current token is read-only. Authenticate with a write-capable token.")
    if args.repo_id.split("/")[0] != identity["name"]:
        raise SystemExit("Use a Space under the authenticated account's username.")
    provider, key_name, key = provider_settings(args.env_file)
    print(f"Account: {identity['name']}; runtime files: {len(runtime_files())}")
    if args.check:
        print("Local deployment prerequisites checked; no Space was changed.")
        return
    api.create_repo(
        args.repo_id, repo_type="space", space_sdk="docker", private=True, exist_ok=True
    )
    info = api.repo_info(args.repo_id, repo_type="space")
    if not info.private:
        raise SystemExit("The target already exists and is public; use a new private Space.")
    api.add_space_secret(args.repo_id, key=key_name, value=key)
    api.add_space_variable(args.repo_id, key="LLM_PROVIDER", value=provider)
    api.add_space_variable(args.repo_id, key="DIARIZATION_BACKEND", value="heuristic")
    api.upload_folder(
        repo_id=args.repo_id,
        repo_type="space",
        folder_path=str(ROOT),
        allow_patterns=UPLOAD_PATTERNS,
        commit_message="Deploy call intelligence Gradio runtime",
    )
    print(f"Build queued: https://huggingface.co/spaces/{args.repo_id}")
    print("Deployment is complete only after the Space reaches RUNNING and smoke checks pass.")


if __name__ == "__main__":
    main()
