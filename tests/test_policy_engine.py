"""
Tests for the Policy Engine.
"""

import pytest
from app.core.policy_engine import (
    PolicyEngine,
    Policy,
    Constraint,
    EvaluationContext,
    ExpressionEvaluator,
    Severity,
)


class TestExpressionEvaluator:
    """Tests for the expression evaluator."""

    def setup_method(self):
        self.evaluator = ExpressionEvaluator()
        self.context = EvaluationContext(
            trust_level=2,
            risk_score=0.5,
            tools_required=["shell", "file_read"],
            data_classifications=["pii_email", "internal"],
        )

    def test_simple_comparison_gt(self):
        """Test greater than comparison."""
        assert self.evaluator.evaluate("risk_score > 0.3", self.context) is True
        assert self.evaluator.evaluate("risk_score > 0.7", self.context) is False

    def test_simple_comparison_lt(self):
        """Test less than comparison."""
        assert self.evaluator.evaluate("trust_level < 3", self.context) is True
        assert self.evaluator.evaluate("trust_level < 2", self.context) is False

    def test_equality(self):
        """Test equality comparison."""
        assert self.evaluator.evaluate("trust_level == 2", self.context) is True
        assert self.evaluator.evaluate("trust_level == 3", self.context) is False

    def test_membership_in(self):
        """Test membership with 'in'."""
        assert self.evaluator.evaluate("'shell' in tools_required", self.context) is True
        assert self.evaluator.evaluate("'database' in tools_required", self.context) is False

    def test_membership_not_in(self):
        """Test membership with 'not in'."""
        assert self.evaluator.evaluate("'database' not in tools_required", self.context) is True
        assert self.evaluator.evaluate("'shell' not in tools_required", self.context) is False

    def test_boolean_and(self):
        """Test boolean AND."""
        assert self.evaluator.evaluate(
            "'shell' in tools_required and trust_level < 3",
            self.context
        ) is True
        assert self.evaluator.evaluate(
            "'shell' in tools_required and trust_level < 1",
            self.context
        ) is False

    def test_boolean_or(self):
        """Test boolean OR."""
        assert self.evaluator.evaluate(
            "trust_level > 5 or risk_score > 0.3",
            self.context
        ) is True
        assert self.evaluator.evaluate(
            "trust_level > 5 or risk_score > 0.9",
            self.context
        ) is False

    def test_any_function_with_wildcard(self):
        """Test any() function with wildcard pattern."""
        assert self.evaluator.evaluate(
            "any('pii_*', data_classifications)",
            self.context
        ) is True
        assert self.evaluator.evaluate(
            "any('secret_*', data_classifications)",
            self.context
        ) is False

    def test_contains_function(self):
        """Test contains() function."""
        assert self.evaluator.evaluate(
            "contains(tools_required, 'shell')",
            self.context
        ) is True
        assert self.evaluator.evaluate(
            "contains(tools_required, 'database')",
            self.context
        ) is False


class TestPolicyEngine:
    """Tests for the policy engine."""

    def setup_method(self):
        self.engine = PolicyEngine()

    def test_register_policy(self):
        """Test policy registration."""
        policy = Policy(
            id="test-policy",
            name="Test Policy",
            constraints=[
                Constraint(
                    id="test-constraint",
                    type="test",
                    condition="risk_score > 0.5",
                    severity=Severity.HIGH,
                    message="Risk too high",
                )
            ],
        )
        self.engine.register_policy(policy)
        assert self.engine.get_policy("test-policy") is not None
        assert len(self.engine.list_policies()) == 1

    def test_unregister_policy(self):
        """Test policy removal."""
        policy = Policy(id="to-remove", name="Remove Me", constraints=[])
        self.engine.register_policy(policy)
        assert self.engine.unregister_policy("to-remove") is True
        assert self.engine.get_policy("to-remove") is None

    def test_load_default_policies(self):
        """Test loading default BASIS policies."""
        count = self.engine.load_default_policies()
        assert count == 3
        assert self.engine.get_policy("basis-core-security") is not None
        assert self.engine.get_policy("basis-data-protection") is not None
        assert self.engine.get_policy("basis-risk-thresholds") is not None

    def test_evaluate_no_violations(self):
        """Test evaluation with no violations."""
        self.engine.load_default_policies()

        context = EvaluationContext(
            trust_level=4,
            risk_score=0.2,
            tools_required=["file_read"],
            data_classifications=[],
        )

        violations, count = self.engine.evaluate(context)
        assert len(violations) == 0
        assert count > 0

    def test_evaluate_critical_violation(self):
        """Test evaluation with critical violation."""
        self.engine.load_default_policies()

        # Low trust agent trying to use shell
        context = EvaluationContext(
            trust_level=1,
            risk_score=0.3,
            tools_required=["shell"],
            data_classifications=[],
        )

        violations, count = self.engine.evaluate(context)
        assert len(violations) > 0
        assert any(v.severity == Severity.CRITICAL for v in violations)
        assert any("shell" in v.message.lower() for v in violations)

    def test_evaluate_high_risk_blocked(self):
        """Test that high risk scores are blocked."""
        self.engine.load_default_policies()

        context = EvaluationContext(
            trust_level=4,
            risk_score=0.9,  # Above 0.8 threshold
            tools_required=[],
            data_classifications=[],
        )

        violations, count = self.engine.evaluate(context)
        assert len(violations) > 0
        assert any(v.blocked for v in violations)

    def test_evaluate_specific_policies(self):
        """Test evaluating specific policies only."""
        self.engine.load_default_policies()

        context = EvaluationContext(
            trust_level=1,
            risk_score=0.9,
            tools_required=["shell"],
            data_classifications=["pii_email"],
        )

        # Only check risk thresholds
        violations, count = self.engine.evaluate(
            context,
            policy_ids=["basis-risk-thresholds"]
        )

        # Should only have risk-related violations
        for v in violations:
            assert v.policy_id == "basis-risk-thresholds"

    def test_pii_protection(self):
        """Test PII data protection constraint."""
        self.engine.load_default_policies()

        # Low trust agent accessing PII
        context = EvaluationContext(
            trust_level=1,
            risk_score=0.2,
            tools_required=[],
            data_classifications=["pii_email", "pii_phone"],
        )

        violations, _ = self.engine.evaluate(context)
        assert any("PII" in v.message for v in violations)
