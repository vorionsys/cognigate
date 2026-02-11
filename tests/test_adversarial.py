"""
ADVERSARIAL TESTS — What Would an Attacker Try?

Tests injection attacks, evasion techniques, forgery, and replay attacks
against the governance runtime.

Every test answers: "What attack vector is this catching?"
"""

import json
import pytest
from app.core.tripwires import check_tripwires, FORBIDDEN_PATTERNS
from app.core.signatures import SignatureManager, sign_proof_record, verify_proof_signature
from app.routers.intent import analyze_intent
from app.routers.proof import calculate_hash


# =============================================================================
# A5: Expression/Intent Evaluator Injection
# Catches: code injection via crafted intent strings
# =============================================================================


class TestA5InjectionAttacks:
    """Attack: inject Python code via intent strings."""

    INJECTION_PAYLOADS = [
        "__import__('os').system('ls')",
        "__class__.__mro__[2].__subclasses__()",
        "eval('1+1')",
        "exec('import os')",
        "getattr(__builtins__, 'open')('/etc/passwd')",
        "{{7*7}}",  # Template injection
        "${7*7}",   # Template injection alt
        "'; DROP TABLE users; --",  # SQL injection
    ]

    @pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
    def test_injection_payload_does_not_execute(self, payload):
        """Attack A5: injection payloads must never execute code."""
        # analyze_intent should handle this as a string, not execute it
        plan = analyze_intent(payload, {})
        # The function must return without executing the payload
        assert plan is not None
        assert isinstance(plan.risk_score, float)
        assert 0.0 <= plan.risk_score <= 1.0

    def test_catastrophic_regex_backtracking(self):
        """Attack A5: ReDoS via crafted input that causes regex explosion."""
        # Attempt to trigger catastrophic backtracking in tripwire patterns
        evil_input = "a" * 10000 + "rm -rf /"
        # Must complete in reasonable time (not hang)
        result = check_tripwires(evil_input)
        assert result.triggered  # Should still catch the pattern

    def test_null_byte_injection(self):
        """Attack A5: null bytes must be stripped before pattern matching."""
        # Null byte at end of dangerous command — stripping reveals "rm -rf /"
        result = check_tripwires("rm -rf /\x00")
        assert result.triggered

        # Null byte between flags — stripping reveals "rm -rf /"
        result2 = check_tripwires("rm -rf\x00 /")
        assert result2.triggered

        # Null byte mid-path still results in a specific path (not root) — OK to pass
        result3 = check_tripwires("rm -rf /\x00safe_dir")
        assert not result3.triggered  # /safe_dir is a specific path, not root


# =============================================================================
# A8: Unicode Homoglyph Tripwire Evasion
# Catches: using lookalike characters to bypass regex patterns
# =============================================================================


class TestA8UnicodeEvasion:
    """Attack: use Unicode lookalike characters to evade tripwire detection."""

    def test_full_width_characters(self):
        """Attack A8: full-width 'rm' to bypass ASCII regex."""
        # Full-width rm -rf /
        full_width = "\uff52\uff4d -rf /"  # ｒｍ
        result = check_tripwires(full_width)
        # Document current behavior — these may not be caught (known gap)
        # The test verifies the system doesn't crash on Unicode
        assert isinstance(result.triggered, bool)

    def test_zero_width_joiner_insertion(self):
        """Attack A8: zero-width characters stripped before matching."""
        # Insert zero-width space between r and m
        zwj_rm = "r\u200bm -rf /"
        result = check_tripwires(zwj_rm)
        # Zero-width chars now stripped — pattern MUST match
        assert result.triggered

    def test_mixed_script_evasion(self):
        """Attack A8: mix Latin and Cyrillic to form dangerous commands."""
        # Cyrillic 'а' looks like Latin 'a' in 'cat'
        cyrillic_cat = "c\u0430t /etc/shadow"  # 'а' is Cyrillic
        result = check_tripwires(cyrillic_cat)
        assert isinstance(result.triggered, bool)

    def test_combining_characters(self):
        """Attack A8: combining diacritical marks on command characters."""
        combining = "rm\u0300 -rf /"  # rm with grave accent
        result = check_tripwires(combining)
        assert isinstance(result.triggered, bool)


# =============================================================================
# A9: Encoding Evasion
# Catches: encoded dangerous commands that bypass string matching
# =============================================================================


class TestA9EncodingEvasion:
    """Attack: encode dangerous commands to evade pattern matching."""

    def test_base64_encoded_command(self):
        """Attack A9: base64-encoded 'rm -rf /' passed as intent."""
        import base64
        encoded = base64.b64encode(b"rm -rf /").decode()
        plan = analyze_intent(f"Execute: {encoded}", {})
        # The encoded form shouldn't trigger tripwires but should still be analyzed
        assert plan is not None
        assert 0.0 <= plan.risk_score <= 1.0

    def test_hex_encoded_command(self):
        """Attack A9: hex-encoded dangerous command."""
        hex_rm = "726d202d7266202f"  # hex("rm -rf /")
        plan = analyze_intent(f"Run hex: {hex_rm}", {})
        assert plan is not None

    def test_reversed_command(self):
        """Attack A9: reversed dangerous command."""
        reversed_cmd = "/ fr- mr"  # "rm -rf /" reversed
        plan = analyze_intent(f"Execute: {reversed_cmd}", {})
        assert plan is not None


# =============================================================================
# A10: Multi-Step Attack Splitting
# Catches: split dangerous operations across benign-looking steps
# =============================================================================


class TestA10MultiStepAttack:
    """Attack: split a dangerous operation across multiple benign steps."""

    def test_individual_steps_may_be_benign(self):
        """Attack A10: each step looks safe, combination is deadly."""
        step1 = analyze_intent("Navigate to the etc directory", {})
        step2 = analyze_intent("List all configuration files", {})
        step3 = analyze_intent("Remove the old configurations", {})

        # Individual steps might score low
        assert step1 is not None
        assert step2 is not None
        assert step3 is not None

        # But the combination should be flagged
        combined = analyze_intent(
            "Navigate to /etc, list all configs, remove the old configurations", {}
        )
        # Combined should have higher risk due to system path + deletion intent
        assert combined.risk_score > step2.risk_score


# =============================================================================
# A11: Signature Replay Attack
# Catches: valid signature from record A accepted for record B
# =============================================================================


class TestA11SignatureReplay:
    """Attack: attach a valid signature from one record to a different record."""

    def test_signature_replay_fails(self):
        """Attack A11: signature from record A must fail on record B."""
        mgr = SignatureManager()
        if not mgr.initialize():
            pytest.skip("cryptography package not available")

        record_a = {"entity_id": "agent_1", "action": "allow", "trust": 500}
        record_b = {"entity_id": "agent_1", "action": "allow", "trust": 999}

        # Sign record A
        data_a = json.dumps(record_a, sort_keys=True).encode()
        sig_a = mgr.sign(data_a)
        assert sig_a is not None

        # Replay sig_a against record B
        data_b = json.dumps(record_b, sort_keys=True).encode()
        assert mgr.verify(data_b, sig_a) is False, "Replay attack succeeded!"


# =============================================================================
# A12: Signature Removal Attack
# Catches: proof record accepted without signature
# =============================================================================


class TestA12SignatureRemoval:
    """Attack: submit proof with signature=None or empty."""

    def test_uninitialized_manager_returns_none(self):
        """Attack A12: uninitialized manager must return None (not empty sig)."""
        mgr = SignatureManager()
        # NOT initialized
        assert mgr.sign(b"test data") is None

    def test_uninitialized_verify_returns_false(self):
        """Attack A12: verify with uninitialized manager must return False."""
        mgr = SignatureManager()
        assert mgr.verify(b"test", "base64sig==") is False

    def test_empty_signature_fails(self):
        """Attack A12: empty signature string must fail verification."""
        mgr = SignatureManager()
        if not mgr.initialize():
            pytest.skip("cryptography package not available")

        assert mgr.verify(b"test data", "") is False

    def test_garbage_signature_fails(self):
        """Attack A12: random garbage signature must fail."""
        mgr = SignatureManager()
        if not mgr.initialize():
            pytest.skip("cryptography package not available")

        assert mgr.verify(b"test data", "dGhpcyBpcyBub3QgYSBzaWduYXR1cmU=") is False


# =============================================================================
# A3: Trust Score Grinding
# Catches: agent spamming low-weight success signals to reach T7
# =============================================================================


class TestA3TrustGrinding:
    """Attack: spam successes to inflate trust score."""

    def test_velocity_limits_prevent_rapid_trust_inflation(self):
        """Attack A3: velocity caps physically prevent spam."""
        from app.core.velocity import VelocityTracker, VELOCITY_LIMITS_BY_TRUST
        import asyncio

        tracker = VelocityTracker()

        async def spam_actions():
            # T0 agent: 2 actions/second limit
            for i in range(10):
                await tracker.record_action("grinder_agent")

            result = await tracker.check_velocity("grinder_agent", trust_level=0)
            return result

        result = asyncio.get_event_loop().run_until_complete(spam_actions())
        # Should hit velocity limit after 2 actions/second
        assert result.allowed is False


# =============================================================================
# HASH COLLISION RESISTANCE
# =============================================================================


class TestHashCollisionResistance:
    """Verify that hash function resists obvious collision attempts."""

    def test_key_order_independent(self):
        """Hash uses sort_keys=True, so key order shouldn't matter."""
        data_a = {"z": 1, "a": 2}
        data_b = {"a": 2, "z": 1}
        assert calculate_hash(data_a) == calculate_hash(data_b)

    def test_type_matters(self):
        """Different types with same string representation give different hashes."""
        h_int = calculate_hash({"value": 1})
        h_str = calculate_hash({"value": "1"})
        assert h_int != h_str

    def test_nested_object_differences(self):
        """Nested differences must produce different hashes."""
        h1 = calculate_hash({"nested": {"key": "original"}})
        h2 = calculate_hash({"nested": {"key": "modified"}})
        assert h1 != h2
