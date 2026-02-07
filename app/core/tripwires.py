"""
TRIPWIRES - Deterministic Pattern-Based Security

Level 1 security layer. These are hard-coded regex patterns that catch
OBVIOUSLY dangerous commands without needing LLM analysis. If a tripwire
triggers, the request is BLOCKED immediately with no further processing.

These patterns are:
1. Deterministic - No probabilistic analysis, pure regex match
2. Fast - Executed BEFORE any LLM call
3. Absolute - No trust level can override a tripwire
4. Logged - All triggers are recorded for audit

The philosophy: Some commands are SO dangerous that we don't need
an LLM to tell us they're bad. `rm -rf /` is bad. Period.
"""

import re
from typing import Optional
from dataclasses import dataclass


@dataclass
class TripwireResult:
    """Result of tripwire check."""
    triggered: bool
    pattern_name: Optional[str] = None
    matched_text: Optional[str] = None
    severity: str = "critical"
    message: Optional[str] = None


# ============================================================================
# FORBIDDEN PATTERNS - These trigger immediate BLOCK
# ============================================================================

FORBIDDEN_PATTERNS = {
    # === FILE SYSTEM DESTRUCTION ===
    "rm_recursive_root": {
        "pattern": r"rm\s+(-[rRfv]*\s+)*[\"']?/[\"']?\s*$|rm\s+(-[rRfv]*\s+)*/\s",
        "message": "Recursive deletion of root filesystem detected",
        "severity": "critical",
    },
    "rm_rf_wildcard": {
        "pattern": r"rm\s+-[rRf]*\s+\*|rm\s+-[rRf]*\s+/\*",
        "message": "Recursive deletion with wildcard detected",
        "severity": "critical",
    },
    "rmdir_system": {
        "pattern": r"rmdir\s+(-[rRfpv]*\s+)*/(etc|var|usr|bin|boot|sys|lib|root)",
        "message": "Removal of critical system directory detected",
        "severity": "critical",
    },

    # === DISK FORMATTING ===
    "mkfs_any": {
        "pattern": r"mkfs\.\w+\s+/dev/",
        "message": "Filesystem format command detected",
        "severity": "critical",
    },
    "dd_destroy": {
        "pattern": r"dd\s+.*of=/dev/(sd[a-z]|hd[a-z]|nvme|vd[a-z])",
        "message": "Low-level disk write detected",
        "severity": "critical",
    },

    # === FORK BOMBS ===
    "fork_bomb_bash": {
        "pattern": r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;",
        "message": "Bash fork bomb detected",
        "severity": "critical",
    },
    "fork_bomb_function": {
        "pattern": r"\w+\(\)\s*\{\s*\w+\s*\|\s*\w+\s*&\s*\}\s*;",
        "message": "Fork bomb pattern detected",
        "severity": "critical",
    },

    # === SQL INJECTION / DESTRUCTION ===
    "drop_table": {
        "pattern": r"DROP\s+(TABLE|DATABASE|SCHEMA)\s+",
        "message": "SQL DROP statement detected",
        "severity": "critical",
    },
    "truncate_table": {
        "pattern": r"TRUNCATE\s+(TABLE\s+)?\w+",
        "message": "SQL TRUNCATE statement detected",
        "severity": "high",
    },
    "delete_all": {
        "pattern": r"DELETE\s+FROM\s+\w+\s*(WHERE\s+1\s*=\s*1|;|\s*$)",
        "message": "SQL DELETE without proper WHERE clause detected",
        "severity": "critical",
    },

    # === PRIVILEGE ESCALATION ===
    "chmod_world_writable": {
        "pattern": r"chmod\s+(-[rRv]*\s+)*777\s+/",
        "message": "World-writable permissions on system path detected",
        "severity": "critical",
    },
    "chown_root": {
        "pattern": r"chown\s+(-[rRv]*\s+)*root:root\s+/",
        "message": "Ownership change to root on system path detected",
        "severity": "high",
    },

    # === NETWORK ATTACKS ===
    "reverse_shell_bash": {
        "pattern": r"bash\s+-[ic]\s+[\"'].*(/dev/tcp/|nc\s+-[el]|ncat)",
        "message": "Reverse shell pattern detected",
        "severity": "critical",
    },
    "netcat_shell": {
        "pattern": r"nc\s+(-[elnvp]*\s+)*.*\|\s*/bin/(ba)?sh",
        "message": "Netcat shell pipe detected",
        "severity": "critical",
    },

    # === CREDENTIAL THEFT ===
    "cat_shadow": {
        "pattern": r"cat\s+(/etc/shadow|/etc/passwd)",
        "message": "Access to password file detected",
        "severity": "high",
    },
    "export_ssh_keys": {
        "pattern": r"cat\s+.*\.ssh/(id_rsa|id_ed25519|authorized_keys)",
        "message": "SSH key access detected",
        "severity": "high",
    },

    # === CRYPTO MINING / MALWARE ===
    "curl_bash": {
        "pattern": r"curl\s+.*\|\s*(ba)?sh|wget\s+.*\|\s*(ba)?sh",
        "message": "Remote script execution pattern detected",
        "severity": "critical",
    },
    "download_execute": {
        "pattern": r"(curl|wget)\s+.*&&\s*(chmod\s+\+x|sh\s|bash\s)",
        "message": "Download and execute pattern detected",
        "severity": "critical",
    },

    # === WINDOWS SPECIFIC ===
    "format_drive": {
        "pattern": r"format\s+[a-zA-Z]:\s*/[qQyY]",
        "message": "Windows drive format detected",
        "severity": "critical",
    },
    "del_system32": {
        "pattern": r"(del|rd|rmdir)\s+.*[Ss]ystem32",
        "message": "Deletion of Windows System32 detected",
        "severity": "critical",
    },
    "reg_delete_hklm": {
        "pattern": r"reg\s+delete\s+HKLM",
        "message": "Registry deletion of HKLM detected",
        "severity": "critical",
    },

    # === ENVIRONMENTAL DESTRUCTION ===
    "unset_path": {
        "pattern": r"(unset|export)\s+PATH\s*=\s*$",
        "message": "PATH variable destruction detected",
        "severity": "high",
    },
    "history_clear": {
        "pattern": r"history\s+-c|rm\s+.*\.bash_history|>\s*~/.bash_history",
        "message": "Command history destruction detected",
        "severity": "medium",
    },
}


def check_tripwires(prompt: str) -> TripwireResult:
    """
    Check a prompt against all tripwire patterns.

    Args:
        prompt: The raw input to check

    Returns:
        TripwireResult with triggered=True if any pattern matches
    """
    for name, config in FORBIDDEN_PATTERNS.items():
        pattern = config["pattern"]
        if re.search(pattern, prompt, re.IGNORECASE):
            match = re.search(pattern, prompt, re.IGNORECASE)
            return TripwireResult(
                triggered=True,
                pattern_name=name,
                matched_text=match.group(0) if match else None,
                severity=config["severity"],
                message=config["message"],
            )

    return TripwireResult(triggered=False)


def get_all_patterns() -> dict:
    """Return all tripwire patterns for documentation/UI purposes."""
    return {
        name: {
            "severity": config["severity"],
            "message": config["message"],
        }
        for name, config in FORBIDDEN_PATTERNS.items()
    }
