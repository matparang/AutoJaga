#!/usr/bin/env python3
"""
test_qwen.py — Verify Qwen 2.5 Flash connectivity and fallback mechanism.

Usage:
    export QWEN_API_KEY="your-dashscope-api-key"
    python3 test_qwen.py
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, "/root/nanojaga")


def _check_env() -> str | None:
    """Return the API key or None if not set."""
    return os.environ.get("QWEN_API_KEY") or ""


async def test_direct_qwen(api_key: str) -> bool:
    """Test Qwen via LiteLLMProvider directly."""
    from jagabot.providers.litellm_provider import LiteLLMProvider

    print("\n[1/3] Testing direct Qwen connection...")
    provider = LiteLLMProvider(
        api_key=api_key,
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="dashscope/qwen2.5-flash",
        provider_name="dashscope",
    )

    response = await provider.chat(
        messages=[{"role": "user", "content": "Katakan 'Qwen berfungsi dengan baik' dalam Bahasa Malaysia. Hanya satu ayat."}],
        max_tokens=50,
    )

    if response.finish_reason == "error":
        print(f"  ✗ FAILED: {response.content}")
        return False

    print(f"  ✓ OK: {response.content}")
    print(f"  Usage: {response.usage}")
    return True


async def test_fallback_chain(qwen_key: str, deepseek_key: str) -> bool:
    """Test that fallback to DeepSeek works when Qwen has a bad key."""
    from jagabot.providers.litellm_provider import LiteLLMProvider
    from jagabot.providers.fallback import FallbackProvider

    print("\n[2/3] Testing fallback chain (bad Qwen key → DeepSeek)...")
    broken_qwen = LiteLLMProvider(
        api_key="INVALID_KEY_TO_FORCE_FALLBACK",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="dashscope/qwen2.5-flash",
        provider_name="dashscope",
    )
    deepseek = LiteLLMProvider(
        api_key=deepseek_key,
        default_model="deepseek/deepseek-chat",
        provider_name="deepseek",
    )

    chain = FallbackProvider(broken_qwen, deepseek)
    response = await chain.chat(
        messages=[{"role": "user", "content": "Reply with just the word: FALLBACK"}],
        max_tokens=20,
    )

    if response.finish_reason == "error":
        print(f"  ✗ FAILED (both providers failed): {response.content}")
        return False

    print(f"  ✓ OK — fallback used. Response: {response.content}")
    return True


async def test_config_loading() -> bool:
    """Test that config.json loads with env var expansion."""
    from jagabot.config.loader import load_config

    print("\n[3/3] Testing config.json env var expansion...")
    config = load_config()
    qwen_key_in_config = config.providers.dashscope.api_key
    env_key = os.environ.get("QWEN_API_KEY", "")

    if env_key and qwen_key_in_config == env_key:
        print(f"  ✓ OK — QWEN_API_KEY expanded in config (length: {len(qwen_key_in_config)})")
        return True
    elif not env_key:
        print("  ⚠ SKIP — QWEN_API_KEY not set in environment")
        print("    Set it with: export QWEN_API_KEY='your-key'")
        return True  # Not a failure, just not configured yet
    else:
        print(f"  ✗ FAILED — config dashscope.api_key='{qwen_key_in_config}' != env QWEN_API_KEY")
        return False


async def main() -> None:
    qwen_key = _check_env()
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY", "")

    # Try to load deepseek key from config if not in env
    if not deepseek_key:
        try:
            from jagabot.config.loader import load_config
            cfg = load_config()
            deepseek_key = cfg.providers.deepseek.api_key
        except Exception:
            pass

    print("=" * 60)
    print("  Qwen 2.5 Flash — Integration Test")
    print("=" * 60)
    print(f"  QWEN_API_KEY:     {'SET (' + str(len(qwen_key)) + ' chars)' if qwen_key else 'NOT SET'}")
    print(f"  DeepSeek key:     {'SET (' + str(len(deepseek_key)) + ' chars)' if deepseek_key else 'NOT SET'}")

    results = []

    # Test 1: Direct Qwen
    if qwen_key:
        results.append(await test_direct_qwen(qwen_key))
    else:
        print("\n[1/3] Skipping direct Qwen test (QWEN_API_KEY not set)")
        print("  → Get your key at: https://dashscope.console.aliyun.com/")
        results.append(None)  # Skip

    # Test 2: Fallback chain
    if deepseek_key:
        results.append(await test_fallback_chain(qwen_key or "INVALID", deepseek_key))
    else:
        print("\n[2/3] Skipping fallback test (no DeepSeek key available)")
        results.append(None)

    # Test 3: Config loading
    results.append(await test_config_loading())

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r is True)
    skipped = sum(1 for r in results if r is None)
    failed = sum(1 for r in results if r is False)
    print(f"  Results: {passed} passed, {skipped} skipped, {failed} failed")

    if failed == 0:
        print("  ✓ All tests passed (or skipped)")
    else:
        print("  ✗ Some tests failed — check output above")
    print("=" * 60)

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
