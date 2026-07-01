"""
hashit — artistic QR code generator
styles: dots, rounded, blocks, gradient, neon, minimal
"""

import io
from typing import Literal
from PIL import Image, ImageDraw, ImageFilter

Style = Literal["dots", "rounded", "blocks", "gradient", "neon", "minimal"]


def _qr_matrix(data: str) -> list[list[bool]]:
    """get raw QR matrix via qrcode lib"""
    import qrcode
    qr = qrcode.QRCode(
        version      = None,
        error_correction = qrcode.constants.ERROR_CORRECT_H,
        box_size     = 1,
        border       = 0,
    )
    qr.add_data(data)
    qr.make(fit=True)
    m = qr.get_matrix()
    return m


def _hex(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))


def _lerp_color(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ── style renderers ────────────────────────────────────────────────────────────

def render_dots(matrix, size, fg, bg, accent) -> Image.Image:
    n    = len(matrix)
    cell = size // (n + 4)
    pad  = (size - cell * n) // 2
    img  = Image.new("RGBA", (size, size), bg + (255,))
    draw = ImageDraw.Draw(img)

    fg_rgb  = fg
    acc_rgb = accent

    for r in range(n):
        for c in range(n):
            if not matrix[r][c]:
                continue
            x = pad + c * cell
            y = pad + r * cell
            # corners get accent color
            is_finder = (
                (r < 7 and c < 7) or
                (r < 7 and c >= n - 7) or
                (r >= n - 7 and c < 7)
            )
            color = acc_rgb if is_finder else fg_rgb
            margin = max(1, cell // 8)
            draw.ellipse(
                [x + margin, y + margin,
                 x + cell - margin - 1,
                 y + cell - margin - 1],
                fill=color + (255,)
            )
    return img


def render_rounded(matrix, size, fg, bg, accent) -> Image.Image:
    n    = len(matrix)
    cell = size // (n + 4)
    pad  = (size - cell * n) // 2
    img  = Image.new("RGBA", (size, size), bg + (255,))
    draw = ImageDraw.Draw(img)

    fg_rgb  = fg
    acc_rgb = accent

    for r in range(n):
        for c in range(n):
            if not matrix[r][c]:
                continue
            x = pad + c * cell
            y = pad + r * cell
            is_finder = (
                (r < 7 and c < 7) or
                (r < 7 and c >= n - 7) or
                (r >= n - 7 and c < 7)
            )
            color = acc_rgb if is_finder else fg_rgb

            # check neighbors for connected rounded rects
            top    = r > 0     and matrix[r-1][c]
            bottom = r < n-1   and matrix[r+1][c]
            left   = c > 0     and matrix[r][c-1]
            right  = c < n-1   and matrix[r][c+1]

            radius = cell // 3 if not (top or bottom or left or right) else cell // 6
            draw.rounded_rectangle(
                [x+1, y+1, x+cell-2, y+cell-2],
                radius=radius,
                fill=color + (255,)
            )
    return img


def render_gradient(matrix, size, fg, bg, accent) -> Image.Image:
    n    = len(matrix)
    cell = size // (n + 4)
    pad  = (size - cell * n) // 2
    img  = Image.new("RGBA", (size, size), bg + (255,))
    draw = ImageDraw.Draw(img)

    c1 = accent
    c2 = fg

    for r in range(n):
        for c in range(n):
            if not matrix[r][c]:
                continue
            x = pad + c * cell
            y = pad + r * cell

            # gradient from top-left to bottom-right
            t     = (r + c) / (2 * n)
            color = _lerp_color(c1, c2, t)
            margin = max(1, cell // 10)

            draw.rounded_rectangle(
                [x + margin, y + margin,
                 x + cell - margin - 1,
                 y + cell - margin - 1],
                radius=cell // 4,
                fill=color + (255,)
            )
    return img


def render_neon(matrix, size, fg, bg, accent) -> Image.Image:
    """neon glow effect — dark bg + bright dots + blur glow layer"""
    n    = len(matrix)
    cell = size // (n + 4)
    pad  = (size - cell * n) // 2

    # base layer
    base = Image.new("RGBA", (size, size), (8, 8, 8, 255))

    # glow layer
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow)

    fg_rgb  = fg
    acc_rgb = accent

    for r in range(n):
        for c in range(n):
            if not matrix[r][c]:
                continue
            x = pad + c * cell
            y = pad + r * cell
            is_finder = (
                (r < 7 and c < 7) or
                (r < 7 and c >= n - 7) or
                (r >= n - 7 and c < 7)
            )
            color = acc_rgb if is_finder else fg_rgb
            # draw large soft dot for glow
            gd.ellipse(
                [x - cell//2, y - cell//2,
                 x + cell + cell//2, y + cell + cell//2],
                fill=color + (60,)
            )

    # blur glow
    glow = glow.filter(ImageFilter.GaussianBlur(radius=cell * 1.5))

    # sharp dots on top
    sharp = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd    = ImageDraw.Draw(sharp)
    for r in range(n):
        for c in range(n):
            if not matrix[r][c]:
                continue
            x = pad + c * cell
            y = pad + r * cell
            is_finder = (
                (r < 7 and c < 7) or
                (r < 7 and c >= n - 7) or
                (r >= n - 7 and c < 7)
            )
            color = acc_rgb if is_finder else fg_rgb
            m = max(1, cell // 8)
            sd.ellipse(
                [x + m, y + m, x + cell - m - 1, y + cell - m - 1],
                fill=color + (255,)
            )

    result = Image.alpha_composite(base, glow)
    result = Image.alpha_composite(result, sharp)
    return result


def render_minimal(matrix, size, fg, bg, accent) -> Image.Image:
    """clean geometric — square dots, extra padding, very minimal"""
    n    = len(matrix)
    cell = size // (n + 6)
    pad  = (size - cell * n) // 2
    img  = Image.new("RGBA", (size, size), bg + (255,))
    draw = ImageDraw.Draw(img)

    fg_rgb  = fg
    acc_rgb = accent

    for r in range(n):
        for c in range(n):
            if not matrix[r][c]:
                continue
            x = pad + c * cell
            y = pad + r * cell
            is_finder = (
                (r < 7 and c < 7) or
                (r < 7 and c >= n - 7) or
                (r >= n - 7 and c < 7)
            )
            color = acc_rgb if is_finder else fg_rgb
            m = max(1, cell // 5)
            draw.rectangle(
                [x + m, y + m, x + cell - m - 1, y + cell - m - 1],
                fill=color + (255,)
            )
    return img


def render_blocks(matrix, size, fg, bg, accent) -> Image.Image:
    """blocky pixel art style — no rounding, tight grid"""
    n    = len(matrix)
    cell = size // (n + 2)
    pad  = (size - cell * n) // 2
    img  = Image.new("RGBA", (size, size), bg + (255,))
    draw = ImageDraw.Draw(img)

    fg_rgb  = fg
    acc_rgb = accent
    tuple(max(0, v - 30) for v in fg_rgb)

    for r in range(n):
        for c in range(n):
            if not matrix[r][c]:
                continue
            x = pad + c * cell
            y = pad + r * cell
            is_finder = (
                (r < 7 and c < 7) or
                (r < 7 and c >= n - 7) or
                (r >= n - 7 and c < 7)
            )
            color = acc_rgb if is_finder else fg_rgb
            draw.rectangle(
                [x, y, x + cell - 1, y + cell - 1],
                fill=color + (255,)
            )
    return img


# ── theme presets ──────────────────────────────────────────────────────────────

THEMES = {
    "dark":    {"fg": "#e8e8e8", "bg": "#0a0a0a", "accent": "#00d46a"},
    "neon":    {"fg": "#00ff88", "bg": "#080808", "accent": "#ff00cc"},
    "fire":    {"fg": "#ff6600", "bg": "#0a0000", "accent": "#ff0000"},
    "ocean":   {"fg": "#4d9eff", "bg": "#040810", "accent": "#00d4ff"},
    "purple":  {"fg": "#cc88ff", "bg": "#080010", "accent": "#ff44cc"},
    "gold":    {"fg": "#ffd700", "bg": "#0a0800", "accent": "#ff8c00"},
    "minimal": {"fg": "#222222", "bg": "#f8f8f8", "accent": "#000000"},
    "matrix":  {"fg": "#00ff41", "bg": "#000000", "accent": "#00aa22"},
}

STYLE_MAP = {
    "dots":     render_dots,
    "rounded":  render_rounded,
    "gradient": render_gradient,
    "neon":     render_neon,
    "minimal":  render_minimal,
    "blocks":   render_blocks,
}


def generate(
    data:   str,
    style:  str = "dots",
    theme:  str = "dark",
    size:   int = 512,
    fg:     str | None = None,
    bg:     str | None = None,
    accent: str | None = None,
) -> bytes:
    matrix   = _qr_matrix(data)
    t        = THEMES.get(theme, THEMES["dark"])
    fg_col   = fg     or t["fg"]
    bg_col   = bg     or t["bg"]
    acc_col  = accent or t["accent"]

    # convert hex strings to rgb tuples for renderers
    fg_col  = _hex(fg_col)  if isinstance(fg_col,  str) else fg_col
    bg_col  = _hex(bg_col)  if isinstance(bg_col,  str) else bg_col
    acc_col = _hex(acc_col) if isinstance(acc_col, str) else acc_col

    renderer = STYLE_MAP.get(style, render_dots)
    img      = renderer(matrix, size, fg_col, bg_col, acc_col)

    # Waifu Mascot centerpiece overlay
    try:
        from pathlib import Path
        mascot_path = Path(__file__).parent.parent / "web" / "static" / "img" / "waifu_mascot.png"
        if mascot_path.exists():
            mascot = Image.open(mascot_path).convert("RGBA")
            m_size = int(size * 0.18)
            mascot = mascot.resize((m_size, m_size), Image.Resampling.LANCZOS)
            pos = ((size - m_size) // 2, (size - m_size) // 2)
            img.paste(mascot, pos, mascot)
    except Exception:
        pass

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.read()
