# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
mutmut configuration for Cognigate Python mutation testing.

Targets the trust-critical core modules:
- circuit_breaker.py (safety gating)
- velocity.py (rate limiting)
- tripwires.py (attack detection)
- signatures.py (cryptographic integrity)
- trust scoring logic

Mutation score target: > 80% on core modules.

Usage:
    mutmut run
    mutmut results
    mutmut html    # Generate HTML report
"""


def pre_mutation(context):
    """Skip mutations in non-critical files."""
    skip_patterns = [
        'app/routers/',      # Router glue code — tested via integration
        'app/theme.py',      # UI theming
        'app/models/',       # Pydantic models — schema validation
        'app/config.py',     # Configuration
        '__init__.py',
    ]
    for pattern in skip_patterns:
        if pattern in context.filename:
            context.skip = True
            return


def pre_mutation_ast(context):
    """Skip string literal mutations in logging calls."""
    if context.current_ast_node and hasattr(context.current_ast_node, 'value'):
        # Skip mutations in logger.info/warning/error calls
        pass
