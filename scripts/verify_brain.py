"""Manual verification script for brain.py.

Run this after Sesi 5-Koreksi to verify brain.py really calls Ollama.

Usage:
    python scripts/verify_brain.py

Exits with code 0 if all checks pass, 1 otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from formpilot.brain import (  # noqa: E402
    UNKNOWN_MARKER,
    _load_prompt_template,
    call_ollama,
    check_ollama_ready,
    resolve_questions,
)
from formpilot.memory.schema import FieldType, Question  # noqa: E402
from formpilot.utils.config_loader import load_config  # noqa: E402


def main() -> int:
    print("=" * 60)
    print("FormPilot Brain Verification")
    print("=" * 60)

    config = load_config("./config/production.yaml")
    print(f"\n[Config] model={config.ollama.model}, url={config.ollama.base_url}")

    # Test 1: Health check
    print("\n[Test 1] Ollama health check...")
    try:
        check_ollama_ready(config)
        print("  PASS: Ollama ready, model available")
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL: {e}")
        return 1

    # Test 2: Raw LLM call
    print("\n[Test 2] Raw LLM call ('Balas satu kata: HALO')...")
    try:
        response = call_ollama(config, "Balas dengan satu kata: HALO")
        print(f"  Response: {response!r}")
        if not response or UNKNOWN_MARKER in response:
            print("  FAIL: empty or UNKNOWN response")
            return 1
        print("  PASS: LLM responded with non-empty text")
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL: {e}")
        return 1

    # Test 3: Resolve personal info (should escalate)
    print("\n[Test 3] Personal info (NIM) -> should escalate to CLI...")
    q_nim = Question(index=0, text="Berapa NIM Anda?", field_type=FieldType.SHORT_TEXT)
    template_text = _load_prompt_template("text_prompt")
    raw_nim_resp = call_ollama(config, template_text.format(question=q_nim.text))
    print(f"  Raw Ollama response: {raw_nim_resp!r}")

    ans = resolve_questions(config, [q_nim])[0]
    print(f"  source={ans.source}, needs_cli={ans.needs_cli}, value={ans.value!r}")
    if not ans.needs_cli:
        print("  FAIL: LLM hallucinated a NIM instead of escalating")
        return 1
    print("  PASS: escalated (no hallucination)")

    # Test 4: Resolve opinion (should answer)
    print("\n[Test 4] Opinion question -> should answer...")
    q_motiv = Question(
        index=0,
        text="Apa motivasi umum orang mengikuti organisasi kampus?",
        field_type=FieldType.PARAGRAPH,
    )
    raw_motiv_resp = call_ollama(config, template_text.format(question=q_motiv.text))
    print(f"  Raw Ollama response: {raw_motiv_resp!r}")

    ans = resolve_questions(config, [q_motiv])[0]
    print(f"  source={ans.source}, needs_cli={ans.needs_cli}, value={ans.value!r}")
    if ans.needs_cli or len(ans.value) < 5:
        print("  FAIL: opinion question not answered properly")
        return 1
    print("  PASS: LLM answered with narrative")

    # Test 5: Resolve radio (must pick valid option)
    print("\n[Test 5] Radio question -> must pick valid option...")
    q_radio = Question(
        index=0,
        text="Pilih yang paling cocok untuk orang yang suka logika:",
        field_type=FieldType.RADIO,
        options=["Seni", "Teknik Informatika", "Sastra"],
    )
    ans = resolve_questions(config, [q_radio])[0]
    print(f"  source={ans.source}, value={ans.value!r}")
    if ans.value not in q_radio.options:
        print(f"  FAIL: answer '{ans.value}' not in options {q_radio.options}")
        return 1
    print("  PASS: LLM picked valid option")

    print("\n" + "=" * 60)
    print("ALL CHECKS PASSED")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
