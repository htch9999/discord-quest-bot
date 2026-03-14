"""
Token masking utility — hide tokens in log output and messages.
"""

import re


# Discord tokens look like: MTI3Nj...base64...
# General pattern: 3 dot-separated base64 segments
_TOKEN_PATTERN = re.compile(
    r"[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{4,10}\.[A-Za-z0-9_-]{20,}"
)


def mask_token(token: str) -> str:
    """Mask a token to only show the last 4 characters."""
    if not token or len(token) <= 4:
        return token
    return f"...{token[-4:]}"


def mask_in_text(text: str) -> str:
    """Replace any token-like patterns in text with masked version."""
    def _replace(match: re.Match) -> str:
        t = match.group(0)
        return f"...{t[-4:]}"

    return _TOKEN_PATTERN.sub(_replace, text)
