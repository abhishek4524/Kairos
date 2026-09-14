"""
test_emotion_tts.py — Tests for emotional SSML generation and emotion tag parsing.

Covers:
  1. parse_emotion_tag — extracts label + strips tag cleanly
  2. get_emotion_profile — resolves known/unknown/alias labels
  3. _build_ssml — validates SSML structure and injects correct prosody params
  4. clean_llm_output — strips [EMOTION:...] from output going to DB
  5. Six sample responses covering different emotions + prosody parameter logging
  6. Fallback behaviour when no emotion tag is emitted
"""

import sys
import os
import pytest

# Ensure backend module root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import importlib.util
from llm_agent import parse_emotion_tag, strip_emotion_tag, clean_llm_output
from tts_emotion_profiles import get_emotion_profile, EMOTION_PROFILES, EMOTION_ALIASES

# Load real tts_agent module directly to bypass conftest.py's sys.modules mock
_tts_spec = importlib.util.spec_from_file_location(
    "real_tts_agent",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tts_agent.py"))
)
_real_tts_agent = importlib.util.module_from_spec(_tts_spec)
_tts_spec.loader.exec_module(_real_tts_agent)
_build_ssml = _real_tts_agent._build_ssml

# ─────────────────────────────────────────────────────────────────────────────
# 1. parse_emotion_tag
# ─────────────────────────────────────────────────────────────────────────────

class TestParseEmotionTag:
    def test_extracts_known_label(self):
        label, text = parse_emotion_tag("[EMOTION:excited]\nHello there!")
        assert label == "excited"
        assert text == "Hello there!"

    def test_extracts_lowercase_label(self):
        label, text = parse_emotion_tag("[EMOTION:calm] Take it easy.")
        assert label == "calm"
        assert text == "Take it easy."

    def test_unknown_label_defaults_to_neutral_but_strips_tag(self):
        label, text = parse_emotion_tag("[EMOTION:rainbow] Something weird.")
        assert label == "neutral"
        assert text == "Something weird."

    def test_no_tag_defaults_to_neutral_and_preserves_text(self):
        label, text = parse_emotion_tag("No tag here at all.")
        assert label == "neutral"
        assert text == "No tag here at all."

    def test_empty_string_defaults_to_neutral(self):
        label, text = parse_emotion_tag("")
        assert label == "neutral"
        assert text == ""

    def test_case_insensitive_label(self):
        label, text = parse_emotion_tag("[EMOTION:URGENT] Warning!")
        assert label == "urgent"
        assert text == "Warning!"

    def test_strips_newline_after_tag(self):
        raw = "[EMOTION:happy]\n\nGood morning, sir!"
        label, text = parse_emotion_tag(raw)
        assert label == "happy"
        assert "EMOTION" not in text

# ─────────────────────────────────────────────────────────────────────────────
# 2. get_emotion_profile
# ─────────────────────────────────────────────────────────────────────────────

class TestGetEmotionProfile:
    def test_known_emotion_returns_correct_rate(self):
        p = get_emotion_profile("excited")
        assert p["rate"] == "+30%"
        assert p["pitch"] == "+4Hz"
        assert p["volume"] == "+8%"

    def test_calm_has_negative_rate(self):
        p = get_emotion_profile("calm")
        # calm should be slower
        assert "-" in p["rate"]
        assert "-" in p["pitch"]

    def test_apologetic_softer_volume(self):
        p = get_emotion_profile("apologetic")
        assert "-" in p["volume"]

    def test_unknown_emotion_returns_neutral(self):
        p = get_emotion_profile("flying_unicorn")
        assert p == EMOTION_PROFILES["neutral"]

    def test_empty_string_returns_neutral(self):
        p = get_emotion_profile("")
        assert p == EMOTION_PROFILES["neutral"]

    def test_alias_sorry_resolves_to_apologetic(self):
        p = get_emotion_profile("sorry")
        assert p == EMOTION_PROFILES["apologetic"]

    def test_alias_normal_resolves_to_neutral(self):
        p = get_emotion_profile("normal")
        assert p == EMOTION_PROFILES["neutral"]

# ─────────────────────────────────────────────────────────────────────────────
# 3. _build_ssml SSML structure
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildSSML:
    VOICE = "en-US-ChristopherNeural"

    def test_valid_xml_structure(self):
        ssml = _build_ssml("Hello world", self.VOICE, "neutral")
        assert ssml.startswith("<speak")
        assert "</speak>" in ssml
        assert f'<voice name="{self.VOICE}">' in ssml
        assert "<prosody" in ssml
        assert "</prosody>" in ssml

    def test_prosody_params_injected_for_excited(self):
        ssml = _build_ssml("Wow!", self.VOICE, "excited")
        profile = get_emotion_profile("excited")
        assert f'rate="{profile["rate"]}"' in ssml
        assert f'pitch="{profile["pitch"]}"' in ssml
        assert f'volume="{profile["volume"]}"' in ssml

    def test_xml_escape_ampersand(self):
        ssml = _build_ssml("fish & chips", self.VOICE, "neutral")
        assert "&amp;" in ssml
        assert "& chips" not in ssml

    def test_xml_escape_angle_brackets(self):
        ssml = _build_ssml("2 < 3 and 4 > 1", self.VOICE, "neutral")
        assert "&lt;" in ssml
        assert "&gt;" in ssml
        assert "< 3" not in ssml

    def test_unknown_emotion_falls_back_to_neutral_prosody(self):
        ssml_unknown = _build_ssml("Hello", self.VOICE, "unknown_emotion")
        ssml_neutral = _build_ssml("Hello", self.VOICE, "neutral")
        # Same prosody params since both resolve to neutral
        assert 'rate="+0%"' in ssml_unknown  # neutral rate
        assert ssml_unknown == ssml_neutral

# ─────────────────────────────────────────────────────────────────────────────
# 4. clean_llm_output strips emotion before DB persistence
# ─────────────────────────────────────────────────────────────────────────────

class TestCleanLLMOutput:
    def test_strips_emotion_tag_from_response(self):
        raw = "[EMOTION:excited]\nGreat, the code works!"
        cleaned = clean_llm_output(raw)
        assert "[EMOTION" not in cleaned
        assert "Great, the code works!" in cleaned

    def test_strips_think_tag_and_emotion(self):
        raw = "<think>reasoning here</think>\n[EMOTION:calm]\nHere is the answer."
        cleaned = clean_llm_output(raw)
        assert "<think>" not in cleaned
        assert "[EMOTION" not in cleaned
        assert "Here is the answer." in cleaned

    def test_no_tag_passes_through_cleanly(self):
        raw = "Just a plain response."
        cleaned = clean_llm_output(raw)
        assert cleaned == "Just a plain response."

# ─────────────────────────────────────────────────────────────────────────────
# 5. Six sample responses covering different emotions with prosody logging
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_RESPONSES = [
    {
        "raw": "[EMOTION:excited]\nYour code compiled and all tests passed! Shippit!",
        "expected_emotion": "excited",
        "expected_text_fragment": "Your code compiled",
    },
    {
        "raw": "[EMOTION:calm]\nHere's a step-by-step explanation of how async/await works in Python.",
        "expected_emotion": "calm",
        "expected_text_fragment": "step-by-step explanation",
    },
    {
        "raw": "[EMOTION:urgent]\nCritical warning: your disk is at 98% capacity. Free up space now.",
        "expected_emotion": "urgent",
        "expected_text_fragment": "Critical warning",
    },
    {
        "raw": "[EMOTION:apologetic]\nI'm sorry, I wasn't able to open that file. Please check the path.",
        "expected_emotion": "apologetic",
        "expected_text_fragment": "sorry",
    },
    {
        "raw": "[EMOTION:thoughtful]\nThat's an interesting design decision. Let me think through the trade-offs.",
        "expected_emotion": "thoughtful",
        "expected_text_fragment": "interesting design",
    },
    {
        "raw": "[EMOTION:confident]\nDone! I've refactored the module and updated all import paths.",
        "expected_emotion": "confident",
        "expected_text_fragment": "Done!",
    },
]


class TestSampleResponses:
    @pytest.mark.parametrize("case", SAMPLE_RESPONSES, ids=[c["expected_emotion"] for c in SAMPLE_RESPONSES])
    def test_parse_and_profile(self, case, capsys):
        label, cleaned_text = parse_emotion_tag(case["raw"])
        profile = get_emotion_profile(label)

        # Verify emotion extracted correctly
        assert label == case["expected_emotion"], (
            f"Expected emotion={case['expected_emotion']}, got {label}"
        )
        # Verify text is clean (no tag)
        assert "[EMOTION" not in cleaned_text
        assert case["expected_text_fragment"] in cleaned_text

        # Verify SSML can be built
        ssml = _build_ssml(cleaned_text, "en-US-ChristopherNeural", label)
        assert f'rate="{profile["rate"]}"' in ssml
        assert f'pitch="{profile["pitch"]}"' in ssml

        # Log prosody parameters (inspect with pytest -s)
        print(
            f"\n[SAMPLE] emotion={label!r:16s} | "
            f"rate={profile['rate']:6s} pitch={profile['pitch']:6s} "
            f"volume={profile['volume']:6s} | text={cleaned_text[:50]!r}"
        )

    @pytest.mark.parametrize("case", SAMPLE_RESPONSES, ids=[c["expected_emotion"] for c in SAMPLE_RESPONSES])
    def test_clean_llm_output_strips_tag(self, case):
        cleaned = clean_llm_output(case["raw"])
        assert "[EMOTION" not in cleaned
        assert case["expected_text_fragment"] in cleaned

# ─────────────────────────────────────────────────────────────────────────────
# 6. Fallback: no emotion tag → neutral profile, no crash
# ─────────────────────────────────────────────────────────────────────────────

class TestFallback:
    def test_no_tag_produces_neutral_ssml(self):
        raw = "Good morning, Abhishek! Ready when you are."
        label, text = parse_emotion_tag(raw)
        assert label == "neutral"
        profile = get_emotion_profile(label)
        ssml = _build_ssml(text, "en-US-ChristopherNeural", label)
        # Neutral rate should be +0%
        assert 'rate="+0%"' in ssml
        assert 'pitch="+0Hz"' in ssml

    def test_garbled_tag_falls_back(self):
        raw = "[EMOTION:]  Some text with empty label."
        label, text = parse_emotion_tag(raw)
        assert label == "neutral"

    def test_strip_emotion_tag_backward_compat(self):
        """strip_emotion_tag still works for code calling the old API."""
        result = strip_emotion_tag("[EMOTION:happy]\nGood morning!")
        assert "[EMOTION" not in result
        assert "Good morning!" in result
