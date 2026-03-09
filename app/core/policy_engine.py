# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Policy Engine for Cognigate.

Evaluates BASIS policies against agent plans using a simple expression language.
Supports loading policies from YAML/JSON files or programmatic registration.
"""

import logging
import operator
import re
from pathlib import Path
from typing import Any, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum

import yaml

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    """Constraint violation severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Constraint:
    """A single policy constraint."""
    id: str
    type: str
    condition: str
    severity: Severity
    message: str
    requires_approval: bool = False
    remediation: Optional[str] = None


@dataclass
class Policy:
    """A BASIS policy with multiple constraints."""
    id: str
    name: str
    description: str = ""
    constraints: list[Constraint] = field(default_factory=list)
    enabled: bool = True


@dataclass
class Violation:
    """A constraint violation result."""
    policy_id: str
    constraint_id: str
    severity: Severity
    message: str
    blocked: bool
    requires_approval: bool = False
    remediation: Optional[str] = None


@dataclass
class EvaluationContext:
    """Context for policy evaluation."""
    trust_level: int
    risk_score: float
    tools_required: list[str]
    data_classifications: list[str]
    estimated_duration: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ExpressionEvaluator:
    """
    Simple expression evaluator for policy conditions.

    Supports:
    - Comparisons: ==, !=, <, >, <=, >=
    - Membership: in, not in
    - Boolean: and, or, not
    - Functions: any(), all(), contains()
    """

    OPERATORS = {
        '==': operator.eq,
        '!=': operator.ne,
        '<': operator.lt,
        '>': operator.gt,
        '<=': operator.le,
        '>=': operator.ge,
    }

    def __init__(self):
        self._functions: dict[str, Callable] = {
            'any': self._any_match,
            'all': self._all_match,
            'contains': self._contains,
            'len': len,
        }

    def evaluate(self, expression: str, context: EvaluationContext) -> bool:
        """
        Evaluate an expression against a context.

        Args:
            expression: The condition expression
            context: The evaluation context

        Returns:
            bool: True if condition is met (violation triggered)
        """
        try:
            # Build the evaluation namespace
            namespace = self._build_namespace(context)

            # Parse and evaluate the expression
            return self._eval_expression(expression, namespace)
        except Exception as e:
            logger.warning(f"Expression evaluation error: {e}, expression: {expression}")
            return False

    def _build_namespace(self, context: EvaluationContext) -> dict[str, Any]:
        """Build namespace for expression evaluation."""
        return {
            'trust_level': context.trust_level,
            'risk_score': context.risk_score,
            'tools_required': context.tools_required,
            'data_classifications': context.data_classifications,
            'estimated_duration': context.estimated_duration,
            **context.metadata,
            **self._functions,
        }

    def _eval_expression(self, expr: str, namespace: dict[str, Any]) -> bool:
        """Evaluate a single expression."""
        expr = expr.strip()

        # Handle 'and' / 'or' boolean operators
        if ' and ' in expr:
            parts = expr.split(' and ', 1)
            return self._eval_expression(parts[0], namespace) and \
                   self._eval_expression(parts[1], namespace)

        if ' or ' in expr:
            parts = expr.split(' or ', 1)
            return self._eval_expression(parts[0], namespace) or \
                   self._eval_expression(parts[1], namespace)

        # Handle 'not' prefix
        if expr.startswith('not '):
            return not self._eval_expression(expr[4:], namespace)

        # Handle 'in' membership test
        if ' in ' in expr and ' not in ' not in expr:
            return self._eval_in(expr, namespace)

        if ' not in ' in expr:
            return not self._eval_in(expr.replace(' not in ', ' in '), namespace)

        # Handle comparisons
        for op_str, op_func in self.OPERATORS.items():
            if op_str in expr:
                return self._eval_comparison(expr, op_str, op_func, namespace)

        # Handle function calls
        if '(' in expr and ')' in expr:
            return self._eval_function(expr, namespace)

        # Handle simple variable lookup (truthy check)
        value = self._resolve_value(expr, namespace)
        return bool(value)

    def _eval_in(self, expr: str, namespace: dict[str, Any]) -> bool:
        """Evaluate 'x in y' expression."""
        parts = expr.split(' in ', 1)
        if len(parts) != 2:
            return False

        item = self._resolve_value(parts[0].strip(), namespace)
        collection = self._resolve_value(parts[1].strip(), namespace)

        if collection is None:
            return False

        return item in collection

    def _eval_comparison(
        self,
        expr: str,
        op_str: str,
        op_func: Callable,
        namespace: dict[str, Any]
    ) -> bool:
        """Evaluate a comparison expression."""
        parts = expr.split(op_str, 1)
        if len(parts) != 2:
            return False

        left = self._resolve_value(parts[0].strip(), namespace)
        right = self._resolve_value(parts[1].strip(), namespace)

        try:
            return op_func(left, right)
        except TypeError:
            return False

    def _eval_function(self, expr: str, namespace: dict[str, Any]) -> bool:
        """Evaluate a function call expression."""
        match = re.match(r'(\w+)\((.*)\)', expr)
        if not match:
            return False

        func_name = match.group(1)
        args_str = match.group(2)

        if func_name not in self._functions:
            return False

        # Parse arguments
        args = [self._resolve_value(a.strip(), namespace) for a in args_str.split(',') if a.strip()]

        return bool(self._functions[func_name](*args))

    def _resolve_value(self, token: str, namespace: dict[str, Any]) -> Any:
        """Resolve a token to its value."""
        token = token.strip()

        # Handle string literals
        if (token.startswith('"') and token.endswith('"')) or \
           (token.startswith("'") and token.endswith("'")):
            return token[1:-1]

        # Handle numeric literals
        try:
            if '.' in token:
                return float(token)
            return int(token)
        except ValueError:
            pass

        # Handle boolean literals
        if token.lower() == 'true':
            return True
        if token.lower() == 'false':
            return False

        # Handle None
        if token.lower() == 'none':
            return None

        # Handle variable lookup
        if token in namespace:
            return namespace[token]

        # Handle dotted access (e.g., metadata.key)
        if '.' in token:
            parts = token.split('.')
            value = namespace.get(parts[0])
            for part in parts[1:]:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    return None
            return value

        return None

    def _any_match(self, pattern: str, collection: list) -> bool:
        """Check if any item in collection matches pattern (with wildcards)."""
        if not collection:
            return False

        if '*' in pattern:
            regex = re.compile(pattern.replace('*', '.*'))
            return any(regex.match(str(item)) for item in collection)
        return pattern in collection

    def _all_match(self, pattern: str, collection: list) -> bool:
        """Check if all items in collection match pattern."""
        if not collection:
            return False

        if '*' in pattern:
            regex = re.compile(pattern.replace('*', '.*'))
            return all(regex.match(str(item)) for item in collection)
        return all(item == pattern for item in collection)

    def _contains(self, collection: list, item: str) -> bool:
        """Check if collection contains item."""
        return item in collection if collection else False


class PolicyEngine:
    """
    The main policy evaluation engine.

    Usage:
        engine = PolicyEngine()
        engine.load_policies_from_file("policies.yaml")

        context = EvaluationContext(
            trust_level=2,
            risk_score=0.5,
            tools_required=["shell", "file_read"],
            data_classifications=["pii_email"],
        )

        violations = engine.evaluate(context)
    """

    def __init__(self):
        self._policies: dict[str, Policy] = {}
        self._evaluator = ExpressionEvaluator()

    def register_policy(self, policy: Policy) -> None:
        """Register a policy with the engine."""
        self._policies[policy.id] = policy
        logger.info(f"Registered policy: {policy.id}")

    def unregister_policy(self, policy_id: str) -> bool:
        """Remove a policy from the engine."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    def get_policy(self, policy_id: str) -> Optional[Policy]:
        """Get a policy by ID."""
        return self._policies.get(policy_id)

    def list_policies(self) -> list[Policy]:
        """List all registered policies."""
        return list(self._policies.values())

    def load_policies_from_file(self, path: str | Path) -> int:
        """
        Load policies from a YAML or JSON file.

        Args:
            path: Path to the policy file

        Returns:
            Number of policies loaded
        """
        path = Path(path)

        if not path.exists():
            logger.warning(f"Policy file not found: {path}")
            return 0

        with open(path) as f:
            if path.suffix in ('.yaml', '.yml'):
                data = yaml.safe_load(f)
            else:
                import json
                data = json.load(f)

        count = 0
        for policy_data in data.get('policies', []):
            policy = self._parse_policy(policy_data)
            if policy:
                self.register_policy(policy)
                count += 1

        logger.info(f"Loaded {count} policies from {path}")
        return count

    def load_default_policies(self) -> int:
        """Load the default BASIS policies."""
        default_policies = [
            Policy(
                id="basis-core-security",
                name="BASIS Core Security",
                description="Core security constraints for agent operations",
                constraints=[
                    Constraint(
                        id="no-shell-low-trust",
                        type="tool_restriction",
                        condition="'shell' in tools_required and trust_level < 3",
                        severity=Severity.CRITICAL,
                        message="Shell execution requires Monitored (T3) trust level",
                    ),
                    Constraint(
                        id="no-delete-without-approval",
                        type="tool_restriction",
                        condition="'file_delete' in tools_required",
                        severity=Severity.HIGH,
                        message="File deletion requires human approval",
                        requires_approval=True,
                    ),
                ],
            ),
            Policy(
                id="basis-data-protection",
                name="BASIS Data Protection",
                description="Data protection and privacy constraints",
                constraints=[
                    Constraint(
                        id="pii-requires-l2",
                        type="data_protection",
                        condition="any('pii_*', data_classifications) and trust_level < 2",
                        severity=Severity.CRITICAL,
                        message="PII access requires Provisional (T2) trust level",
                    ),
                    Constraint(
                        id="credentials-audit",
                        type="data_protection",
                        condition="'credentials' in data_classifications",
                        severity=Severity.HIGH,
                        message="Credential access requires audit logging",
                    ),
                ],
            ),
            Policy(
                id="basis-risk-thresholds",
                name="BASIS Risk Thresholds",
                description="Risk score evaluation thresholds",
                constraints=[
                    Constraint(
                        id="high-risk-block",
                        type="risk_threshold",
                        condition="risk_score > 0.8",
                        severity=Severity.CRITICAL,
                        message="Risk score exceeds maximum threshold (0.8)",
                    ),
                    Constraint(
                        id="medium-risk-escalate",
                        type="risk_threshold",
                        condition="risk_score > 0.5 and trust_level < 3",
                        severity=Severity.HIGH,
                        message="Medium-high risk requires elevated trust or approval",
                        requires_approval=True,
                    ),
                ],
            ),
        ]

        for policy in default_policies:
            self.register_policy(policy)

        return len(default_policies)

    def _parse_policy(self, data: dict) -> Optional[Policy]:
        """Parse a policy from dictionary data."""
        try:
            constraints = []
            for c in data.get('constraints', []):
                constraints.append(Constraint(
                    id=c['id'],
                    type=c.get('type', 'general'),
                    condition=c['condition'],
                    severity=Severity(c.get('severity', 'medium')),
                    message=c['message'],
                    requires_approval=c.get('requires_approval', False),
                    remediation=c.get('remediation'),
                ))

            return Policy(
                id=data['id'],
                name=data['name'],
                description=data.get('description', ''),
                constraints=constraints,
                enabled=data.get('enabled', True),
            )
        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to parse policy: {e}")
            return None

    def evaluate(
        self,
        context: EvaluationContext,
        policy_ids: Optional[list[str]] = None,
    ) -> tuple[list[Violation], int]:
        """
        Evaluate policies against a context.

        Args:
            context: The evaluation context
            policy_ids: Specific policies to evaluate (None = all)

        Returns:
            Tuple of (violations list, constraints evaluated count)
        """
        violations = []
        constraints_evaluated = 0

        policies = self._policies.values()
        if policy_ids:
            policies = [p for p in policies if p.id in policy_ids]

        for policy in policies:
            if not policy.enabled:
                continue

            for constraint in policy.constraints:
                constraints_evaluated += 1

                if self._evaluator.evaluate(constraint.condition, context):
                    violations.append(Violation(
                        policy_id=policy.id,
                        constraint_id=constraint.id,
                        severity=constraint.severity,
                        message=constraint.message,
                        blocked=constraint.severity == Severity.CRITICAL,
                        requires_approval=constraint.requires_approval,
                        remediation=constraint.remediation,
                    ))

        return violations, constraints_evaluated


# Global policy engine instance
policy_engine = PolicyEngine()
