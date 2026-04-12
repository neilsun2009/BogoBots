#!/usr/bin/env python
"""
Simple smoke test for BogoBots.utils.llm_utils.get_llm_client.

Examples:
  python scripts/test_llm_client.py
  python scripts/test_llm_client.py --model "openai/gpt-5.4-mini" --prompt "Say hello in one sentence."
"""

import argparse
import os
import sys
from openai import OpenAI
from typing import Optional
import traceback


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

def get_llm_client(model_name: str, api_key: Optional[str] = None):
    """
    Get an OpenAI-compatible client (official OpenAI package).
    Uses OpenRouter by default.
    """
    import streamlit as st
    
    # Default to OpenRouter
    base_url = "https://openrouter.ai/api/v1"
    default_api_key = st.secrets.get('open_router_key', '')
    
    
    # Check if it's a Qwen model (uses different base URL)
    # if 'qwen' in model_name.lower():
    #     base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    #     default_api_key = st.secrets.get('DASHSCOPE_API_KEY', '')
    
    # # Check if it's an OpenAI official model
    # if model_name.startswith('gpt-') or model_name.startswith('o1'):
    #     base_url = "https://api.openai.com/v1"
    #     default_api_key = st.secrets.get('OPENAI_API_KEY', '')
    
    api_key = api_key or default_api_key
    
    return OpenAI(api_key=api_key, base_url=base_url)


def main() -> int:
    parser = argparse.ArgumentParser(description="Test llm_utils.get_llm_client")
    parser.add_argument("--model", default="openai/gpt-oss-120b", help="Model name")
    parser.add_argument("--prompt", default="Reply with: 'llm client works'.", help="Prompt text")
    parser.add_argument("--max-tokens", type=int, default=100, help="Max tokens")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature")
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENROUTER_API_KEY") or os.getenv("openrouter_api_key"),
        help="API key (default: OPENROUTER_API_KEY env)",
    )
    args = parser.parse_args()

    # if not args.api_key:
    #     print("Missing API key. Set OPENROUTER_API_KEY or pass --api-key.")
    #     return 1

    # from BogoBots.utils.llm_utils import get_llm_client

    try:
        client = get_llm_client(model_name=args.model)
        response = client.chat.completions.create(
            model=args.model,
            messages=[
                {"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": args.prompt},
            ],
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )

        content = (response.choices[0].message.content or "").strip()
        usage = response.usage
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)

        print("=== LLM Client Test Success ===")
        print(f"Model: {args.model}")
        print(f"Prompt tokens: {prompt_tokens}")
        print(f"Completion tokens: {completion_tokens}")
        print("Response:")
        print(content)
        return 0
    except Exception as exc:
        print("=== LLM Client Test Failed ===")
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

