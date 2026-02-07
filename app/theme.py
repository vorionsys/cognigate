"""
Unified Theme System for Cognigate
Mirror of @vorionsys/shared-constants/themes.ts

QUICK SWAP: Change ACTIVE_THEME to switch the entire site's look.
"""

# =============================================================================
# ACTIVE THEME — CHANGE THIS ONE LINE TO SWAP THE SITE
# =============================================================================

ACTIVE_THEME = "midnight_cyan"

# =============================================================================
# THEME DEFINITIONS
# =============================================================================

THEMES = {
    # ═══════════════════════════════════════════════════════════════
    # OPTION 1: MIDNIGHT CYAN — Current look, standardized
    # ═══════════════════════════════════════════════════════════════
    "midnight_cyan": {
        "name": "Midnight Cyan",
        "description": "Developer-native. Terminal-adjacent. The current look, unified.",
        "bg_primary": "#0a0a0f",
        "bg_surface": "#111118",
        "bg_input": "#0d0d14",
        "bg_nav": "#111118",
        "bg_code": "#0d0d14",
        "accent": "#06b6d4",
        "accent_hover": "#22d3ee",
        "accent_muted": "rgba(6, 182, 212, 0.1)",
        "accent_subtle": "rgba(6, 182, 212, 0.03)",
        "text_primary": "#e0e0e6",
        "text_heading": "#ffffff",
        "text_secondary": "#888888",
        "text_tertiary": "#666666",
        "border": "#1e1e2e",
        "border_input": "#2a2a3a",
        "border_hover": "rgba(6, 182, 212, 0.4)",
        "border_divider": "rgba(255, 255, 255, 0.05)",
        "gradient_from": "#06b6d4",
        "gradient_to": "#2dd4bf",
        "scroll_track": "#0a0a0f",
        "scroll_thumb": "#333340",
        "scroll_thumb_hover": "#06b6d4",
        "selection_bg": "rgba(6, 182, 212, 0.3)",
        "success": "#22c55e",
        "error": "#ef4444",
        "warning": "#f97316",
        "info": "#3b82f6",
        "layer_basis": "#fbbf24",
        "layer_intent": "#60a5fa",
        "layer_enforce": "#818cf8",
        "layer_proof": "#34d399",
        "font_family": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        "card_blur": False,
        "button_text": "#000000",
    },

    # ═══════════════════════════════════════════════════════════════
    # OPTION 2: INDIGO AUTHORITY — Governance-forward, institutional
    # ═══════════════════════════════════════════════════════════════
    "indigo_authority": {
        "name": "Indigo Authority",
        "description": "Institutional. Authoritative. Governance-forward.",
        "bg_primary": "#07070d",
        "bg_surface": "#12121f",
        "bg_input": "#0c0c18",
        "bg_nav": "#12121f",
        "bg_code": "#0c0c18",
        "accent": "#818cf8",
        "accent_hover": "#a5b4fc",
        "accent_muted": "rgba(129, 140, 248, 0.1)",
        "accent_subtle": "rgba(129, 140, 248, 0.03)",
        "text_primary": "#dcdce6",
        "text_heading": "#ffffff",
        "text_secondary": "#8888a0",
        "text_tertiary": "#666680",
        "border": "#1e1e30",
        "border_input": "#2a2a40",
        "border_hover": "rgba(129, 140, 248, 0.4)",
        "border_divider": "rgba(255, 255, 255, 0.05)",
        "gradient_from": "#818cf8",
        "gradient_to": "#c084fc",
        "scroll_track": "#07070d",
        "scroll_thumb": "#2a2a40",
        "scroll_thumb_hover": "#818cf8",
        "selection_bg": "rgba(129, 140, 248, 0.3)",
        "success": "#22c55e",
        "error": "#ef4444",
        "warning": "#f97316",
        "info": "#3b82f6",
        "layer_basis": "#fbbf24",
        "layer_intent": "#60a5fa",
        "layer_enforce": "#818cf8",
        "layer_proof": "#34d399",
        "font_family": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        "card_blur": False,
        "button_text": "#000000",
    },

    # ═══════════════════════════════════════════════════════════════
    # OPTION 3: OBSIDIAN AMBER — Warm, premium, "gold standard"
    # ═══════════════════════════════════════════════════════════════
    "obsidian_amber": {
        "name": "Obsidian Amber",
        "description": "Premium. Warm. The gold standard of AI governance.",
        "bg_primary": "#0a0a08",
        "bg_surface": "#141410",
        "bg_input": "#0d0d0a",
        "bg_nav": "#141410",
        "bg_code": "#0d0d0a",
        "accent": "#f59e0b",
        "accent_hover": "#fbbf24",
        "accent_muted": "rgba(245, 158, 11, 0.1)",
        "accent_subtle": "rgba(245, 158, 11, 0.03)",
        "text_primary": "#e6e0d6",
        "text_heading": "#ffffff",
        "text_secondary": "#8a8478",
        "text_tertiary": "#666058",
        "border": "#2a2820",
        "border_input": "#3a3830",
        "border_hover": "rgba(245, 158, 11, 0.4)",
        "border_divider": "rgba(255, 255, 255, 0.05)",
        "gradient_from": "#f59e0b",
        "gradient_to": "#f97316",
        "scroll_track": "#0a0a08",
        "scroll_thumb": "#3a3830",
        "scroll_thumb_hover": "#f59e0b",
        "selection_bg": "rgba(245, 158, 11, 0.3)",
        "success": "#22c55e",
        "error": "#ef4444",
        "warning": "#f97316",
        "info": "#3b82f6",
        "layer_basis": "#fbbf24",
        "layer_intent": "#60a5fa",
        "layer_enforce": "#818cf8",
        "layer_proof": "#34d399",
        "font_family": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        "card_blur": False,
        "button_text": "#000000",
    },

    # ═══════════════════════════════════════════════════════════════
    # OPTION 4: ARCTIC GLASS — Modern SaaS, frosted glass
    # ═══════════════════════════════════════════════════════════════
    "arctic_glass": {
        "name": "Arctic Glass",
        "description": "Modern SaaS. Clean. Frosted glass depth.",
        "bg_primary": "#0c0c14",
        "bg_surface": "rgba(255, 255, 255, 0.04)",
        "bg_input": "rgba(0, 0, 0, 0.3)",
        "bg_nav": "rgba(12, 12, 20, 0.8)",
        "bg_code": "rgba(0, 0, 0, 0.3)",
        "accent": "#38bdf8",
        "accent_hover": "#7dd3fc",
        "accent_muted": "rgba(56, 189, 248, 0.1)",
        "accent_subtle": "rgba(56, 189, 248, 0.03)",
        "text_primary": "#e2e8f0",
        "text_heading": "#f8fafc",
        "text_secondary": "#94a3b8",
        "text_tertiary": "#64748b",
        "border": "rgba(255, 255, 255, 0.08)",
        "border_input": "rgba(255, 255, 255, 0.12)",
        "border_hover": "rgba(56, 189, 248, 0.4)",
        "border_divider": "rgba(255, 255, 255, 0.05)",
        "gradient_from": "#38bdf8",
        "gradient_to": "#06b6d4",
        "scroll_track": "#0c0c14",
        "scroll_thumb": "rgba(255, 255, 255, 0.1)",
        "scroll_thumb_hover": "#38bdf8",
        "selection_bg": "rgba(56, 189, 248, 0.3)",
        "success": "#22c55e",
        "error": "#ef4444",
        "warning": "#f97316",
        "info": "#3b82f6",
        "layer_basis": "#fbbf24",
        "layer_intent": "#60a5fa",
        "layer_enforce": "#818cf8",
        "layer_proof": "#34d399",
        "font_family": "'Geist', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        "card_blur": True,
        "button_text": "#000000",
    },
}


def get_active_theme() -> dict:
    """Get the currently active theme tokens."""
    return THEMES[ACTIVE_THEME]


def theme_to_css_vars(theme_id: str = None) -> str:
    """Generate CSS custom properties from a theme."""
    t = THEMES[theme_id or ACTIVE_THEME]
    return f"""
    --bg-primary: {t['bg_primary']};
    --bg-surface: {t['bg_surface']};
    --bg-input: {t['bg_input']};
    --bg-nav: {t['bg_nav']};
    --bg-code: {t['bg_code']};
    --accent: {t['accent']};
    --accent-hover: {t['accent_hover']};
    --accent-muted: {t['accent_muted']};
    --accent-subtle: {t['accent_subtle']};
    --text-primary: {t['text_primary']};
    --text-heading: {t['text_heading']};
    --text-secondary: {t['text_secondary']};
    --text-tertiary: {t['text_tertiary']};
    --border: {t['border']};
    --border-input: {t['border_input']};
    --border-hover: {t['border_hover']};
    --border-divider: {t['border_divider']};
    --gradient-from: {t['gradient_from']};
    --gradient-to: {t['gradient_to']};
    --scroll-track: {t['scroll_track']};
    --scroll-thumb: {t['scroll_thumb']};
    --scroll-thumb-hover: {t['scroll_thumb_hover']};
    --selection-bg: {t['selection_bg']};
    --success: {t['success']};
    --error: {t['error']};
    --warning: {t['warning']};
    --info: {t['info']};
    --layer-basis: {t['layer_basis']};
    --layer-intent: {t['layer_intent']};
    --layer-enforce: {t['layer_enforce']};
    --layer-proof: {t['layer_proof']};
    --btn-text: {t['button_text']};
    """.strip()
