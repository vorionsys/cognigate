"""
Generate CSS variable blocks for all 4 themes.

Usage:
    python scripts/generate_theme_css.py [theme_id]

If theme_id is provided, outputs just that theme's :root block.
If no argument, outputs all 4 themes as named blocks you can paste into globals.css.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.theme import THEMES, theme_to_css_vars


def generate_css_block(theme_id: str) -> str:
    t = THEMES[theme_id]
    css_vars = theme_to_css_vars(theme_id)
    return f"""/* === {t['name'].upper()} ===
 * {t['description']}
 * To activate: set ACTIVE_THEME = "{theme_id}"
 */
:root {{
  {css_vars}
}}"""


if __name__ == "__main__":
    if len(sys.argv) > 1:
        tid = sys.argv[1]
        if tid not in THEMES:
            print(f"Unknown theme: {tid}")
            print(f"Available: {', '.join(THEMES.keys())}")
            sys.exit(1)
        print(generate_css_block(tid))
    else:
        print("/* ==========================================================================")
        print(" * VORION UNIFIED THEME SYSTEM — All 4 Theme Blocks")
        print(" * Copy the :root block you want into your globals.css")
        print(" * ==========================================================================")
        print(" */\n")
        for tid in THEMES:
            print(generate_css_block(tid))
            print()
