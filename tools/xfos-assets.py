#!/usr/bin/env python3
"""Generate the static xfOS chrome for the profile README.

Writes assets/banner.svg, assets/stack.svg, assets/footer.svg and the
assets/hdr-*.svg section headers. These change rarely — rerun by hand after
editing the copy or the palette below:

    python3 tools/xfos-assets.py

Live numbers are handled separately by tools/xfos-cards.py.
"""
import base64
import math
import pathlib
import random
import urllib.request

AVATAR_URL = "https://avatars.githubusercontent.com/u/53091080?v=4&s=200"

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
OUT.mkdir(parents=True, exist_ok=True)

BG    = "#04090C"
PANEL = "#071319"
LINE  = "#0E3A47"
LINE2 = "#10505F"
CYAN  = "#22E6FF"
CYAND = "#0FB9D6"
DIM   = "#4C7480"
TEXT  = "#CFE6EC"
AMBER = "#FFB020"
RED   = "#FF3355"
GREEN = "#39FF8F"

MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"


def defs_common(w, h, uid):
    """Scanlines + hex grid + vignette + clip, namespaced by uid."""
    return f"""
  <defs>
    <pattern id="scan{uid}" width="3" height="3" patternUnits="userSpaceOnUse">
      <line x1="0" y1="2.5" x2="3" y2="2.5" stroke="{CYAN}" stroke-opacity="0.045" stroke-width="1"/>
    </pattern>
    <pattern id="grid{uid}" width="34" height="20" patternUnits="userSpaceOnUse">
      <path d="M0 10 L8.5 0 L25.5 0 L34 10 L25.5 20 L8.5 20 Z" fill="none"
            stroke="{CYAN}" stroke-opacity="0.05" stroke-width="0.8"/>
    </pattern>
    <linearGradient id="vig{uid}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#000" stop-opacity="0.55"/>
      <stop offset="22%" stop-color="#000" stop-opacity="0"/>
      <stop offset="78%" stop-color="#000" stop-opacity="0"/>
      <stop offset="100%" stop-color="#000" stop-opacity="0.6"/>
    </linearGradient>
    <linearGradient id="glow{uid}" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="{CYAN}" stop-opacity="0"/>
      <stop offset="50%" stop-color="{CYAN}" stop-opacity="0.85"/>
      <stop offset="100%" stop-color="{CYAN}" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="clip{uid}"><rect x="0" y="0" width="{w}" height="{h}"/></clipPath>
  </defs>"""


def backdrop(w, h, uid):
    return f"""
  <g clip-path="url(#clip{uid})">
    <rect width="{w}" height="{h}" fill="{BG}"/>
    <rect width="{w}" height="{h}" fill="url(#grid{uid})"/>
    <rect width="{w}" height="{h}" fill="url(#scan{uid})"/>
    <rect width="{w}" height="{h}" fill="url(#vig{uid})"/>
  </g>"""


def corners(x, y, w, h, size=16, color=CYAN, sw=2):
    r = x + w
    b = y + h
    return f"""
  <g stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="square">
    <path d="M{x},{y+size} L{x},{y} L{x+size},{y}"/>
    <path d="M{r-size},{y} L{r},{y} L{r},{y+size}"/>
    <path d="M{r},{b-size} L{r},{b} L{r-size},{b}"/>
    <path d="M{x+size},{b} L{x},{b} L{x},{b-size}"/>
  </g>"""


# ---------------------------------------------------------------- banner ----
def fetch_avatar() -> str:
    req = urllib.request.Request(AVATAR_URL, headers={"User-Agent": "xfOS-assets"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return base64.b64encode(r.read()).decode()


def banner():
    W, H = 1000, 356
    avatar = fetch_avatar()

    meters = [
        ("CLOUD / IaC",     0.92),
        ("OBSERVABILITY",   0.80),
        ("BACKEND / API",   0.86),
        ("SEC / HARDENING", 0.74),
    ]
    mrows = []
    my = 234
    for i, (label, pct) in enumerate(meters):
        yy = my + i * 22
        full = 268
        val = round(full * pct)
        cells = ""
        n = 22
        cw = full / n
        for c in range(n):
            on = c < round(n * pct)
            cells += (
                f'<rect x="{404 + c*cw:.1f}" y="{yy-9}" width="{cw-2.2:.1f}" height="10" '
                f'fill="{CYAN if on else "#0C2A33"}" opacity="{0.9 if on else 1}">'
                + (f'<animate attributeName="opacity" values="0;0.9" begin="{0.25 + c*0.035:.2f}s" dur="0.2s" fill="freeze"/>' if on else "")
                + "</rect>"
            )
        mrows.append(
            f'<text x="240" y="{yy}" font-size="12.5" fill="{DIM}" letter-spacing="1.4">{label}</text>'
            f'{cells}'
            f'<text x="686" y="{yy}" font-size="12" fill="{CYAND}">{int(pct*100)}%</text>'
        )
    mrows = "\n    ".join(mrows)

    # right-hand telemetry waveform
    random.seed(7)
    pts = []
    for i in range(58):
        x = 740 + i * 4
        base = 262
        y = base - (math.sin(i / 3.4) * 9 + random.uniform(-4, 4))
        if i in (18, 19, 20):
            y = base - 26
        pts.append(f"{x:.0f},{y:.1f}")
    wave = " ".join(pts)

    ticker = ("SYS// UPLINK STABLE   ///   NODE: MADRID-01   ///   INFRA: TERRAFORM + K8S   ///   "
              "PIPELINE: GREEN   ///   TELEMETRY: OTEL   ///   HOST: xavifortes.com   ///   ")
    # monospace advance at 11px + 1.6 letter-spacing; shift exactly one copy for a seamless loop
    tick_w = len(ticker) * (11 * 0.6 + 1.6)
    tick_dur = round(tick_w / 70, 1)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 {W} {H}" width="{W}" height="{H}"
     font-family="{MONO}" role="img" aria-label="xfOS profiler card for Xavi Fortes">
{defs_common(W, H, "B")}
  <defs>
    <clipPath id="avClip"><rect x="34" y="76" width="168" height="168"/></clipPath>
    <clipPath id="tickClip"><rect x="0" y="322" width="{W}" height="34"/></clipPath>
    <clipPath id="nameClip"><rect x="236" y="84" width="470" height="46"/></clipPath>
  </defs>
{backdrop(W, H, "B")}

  <!-- frame -->
  <rect x="1.5" y="1.5" width="{W-3}" height="{H-3}" fill="none" stroke="{LINE2}" stroke-width="1.5"/>
{corners(10, 10, W-20, H-20, 22, CYAN, 2.2)}

  <!-- header strip -->
  <rect x="10" y="10" width="{W-20}" height="34" fill="{CYAN}" fill-opacity="0.06"/>
  <line x1="10" y1="44" x2="{W-10}" y2="44" stroke="{LINE2}" stroke-width="1"/>
  <text x="30" y="32" font-size="14" fill="{CYAN}" letter-spacing="2.6">xfOS &#9656; PROFILER</text>
  <text x="212" y="32" font-size="11.5" fill="{DIM}" letter-spacing="2">v2.14 / REAL-TIME SUBJECT ANALYSIS</text>
  <circle cx="906" cy="26" r="4.5" fill="{RED}">
    <animate attributeName="opacity" values="1;0.1;1" dur="1.15s" repeatCount="indefinite"/>
  </circle>
  <text x="918" y="31" font-size="12" fill="#FF8FA3" letter-spacing="2">REC</text>
  <text x="700" y="31" font-size="11" fill="{DIM}">SESSION 0xA53F19E2</text>

  <!-- sweeping scan line -->
  <g clip-path="url(#clipB)">
    <rect x="0" y="46" width="{W}" height="2" fill="url(#glowB)" opacity="0">
      <animate attributeName="y" values="46;318;46" dur="7s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0;0.9;0" dur="7s" repeatCount="indefinite"/>
    </rect>
  </g>

  <!-- subject image -->
  <rect x="34" y="76" width="168" height="168" fill="{PANEL}"/>
  <image x="34" y="76" width="168" height="168" clip-path="url(#avClip)" opacity="0.92"
         xlink:href="data:image/jpeg;base64,{avatar}"
         href="data:image/jpeg;base64,{avatar}" preserveAspectRatio="xMidYMid slice"/>
  <g clip-path="url(#avClip)">
    <rect x="34" y="76" width="168" height="168" fill="{CYAN}" fill-opacity="0.10"/>
    <rect x="34" y="76" width="168" height="3" fill="{CYAN}" opacity="0.75">
      <animate attributeName="y" values="76;241;76" dur="3.6s" repeatCount="indefinite"/>
    </rect>
    <rect x="34" y="76" width="168" height="168" fill="url(#scanB)"/>
  </g>
{corners(34, 76, 168, 168, 16, CYAN, 2)}
  <rect x="34" y="252" width="168" height="18" fill="{CYAN}" fill-opacity="0.10"/>
  <text x="42" y="265" font-size="10.5" fill="{CYAN}" letter-spacing="1.6">UID 53091080</text>
  <circle cx="39" cy="286" r="4" fill="{GREEN}">
    <animate attributeName="opacity" values="1;0.25;1" dur="2.2s" repeatCount="indefinite"/>
  </circle>
  <text x="50" y="290" font-size="10.5" fill="{GREEN}" letter-spacing="1.4">MATCH 99.7%</text>
  <text x="34" y="310" font-size="10.5" fill="{DIM}" letter-spacing="1.4">SRC / camera-04</text>

  <!-- name with glitch layers -->
  <g clip-path="url(#nameClip)">
    <text x="238" y="118" font-size="38" fill="{RED}" letter-spacing="1.5" opacity="0">
      XAVI FORTES
      <animate attributeName="opacity" values="0;0;0.55;0;0" keyTimes="0;0.86;0.885;0.91;1" dur="6s" repeatCount="indefinite"/>
      <animate attributeName="x" values="238;234;241;238" keyTimes="0;0.87;0.9;1" dur="6s" repeatCount="indefinite"/>
    </text>
    <text x="242" y="118" font-size="38" fill="{CYAN}" letter-spacing="1.5" opacity="0">
      XAVI FORTES
      <animate attributeName="opacity" values="0;0;0.5;0;0" keyTimes="0;0.88;0.9;0.925;1" dur="6s" repeatCount="indefinite"/>
    </text>
    <text x="240" y="118" font-size="38" fill="{TEXT}" letter-spacing="1.5">XAVI FORTES</text>
  </g>
  <text x="242" y="140" font-size="13" fill="{CYAND}" letter-spacing="2.2">@XaviFortes</text>
  <rect x="240" y="152" width="466" height="1" fill="{LINE}"/>

  <g font-size="13">
    <text x="240" y="176" fill="{DIM}" letter-spacing="1.6">OCCUPATION</text>
    <text x="404" y="176" fill="{TEXT}">Cloud Consultant &#183; Platform &amp; DevSecOps Engineer</text>
    <text x="240" y="198" fill="{DIM}" letter-spacing="1.6">LAST SEEN</text>
    <text x="404" y="198" fill="{TEXT}">Madrid, ES &#183; on the grid since 2019</text>
  </g>
  <rect x="240" y="212" width="466" height="1" fill="{LINE}"/>

  <!-- meters -->
  <g>
    {mrows}
  </g>

  <!-- right telemetry column -->
  <line x1="720" y1="76" x2="720" y2="310" stroke="{LINE}" stroke-width="1"/>
  <text x="740" y="96" font-size="11" fill="{DIM}" letter-spacing="2">SIGNAL / TELEMETRY</text>
  <g font-size="12">
    <text x="740" y="126" fill="{DIM}">TUNNEL</text>
    <text x="884" y="126" fill="{GREEN}">SECURE</text>
    <text x="740" y="150" fill="{DIM}">TRACE</text>
    <text x="884" y="150" fill="{AMBER}">SAMPLED</text>
    <text x="740" y="174" fill="{DIM}">DEPLOY</text>
    <text x="884" y="174" fill="{GREEN}">PASSING</text>
    <text x="740" y="198" fill="{DIM}">NOISE</text>
    <text x="884" y="198" fill="{CYAN}">LOW</text>
  </g>
  <rect x="740" y="214" width="228" height="1" fill="{LINE}"/>
  <polyline points="{wave}" fill="none" stroke="{CYAN}" stroke-width="1.6" stroke-opacity="0.9"/>
  <rect x="740" y="232" width="3" height="48" fill="{CYAN}" opacity="0.5">
    <animate attributeName="x" values="740;964;740" dur="4.5s" repeatCount="indefinite"/>
  </rect>
  <text x="740" y="304" font-size="10.5" fill="{DIM}" letter-spacing="1.4">PACKET LOSS 0.00% &#183; RTT 12ms</text>

  <!-- ticker -->
  <rect x="10" y="322" width="{W-20}" height="24" fill="{CYAN}" fill-opacity="0.05"/>
  <line x1="10" y1="322" x2="{W-10}" y2="322" stroke="{LINE}" stroke-width="1"/>
  <g clip-path="url(#tickClip)">
    <g font-size="11" fill="{DIM}" letter-spacing="1.6">
      <text x="20" y="338">{ticker}{ticker}
        <animateTransform attributeName="transform" type="translate" from="0 0" to="-{tick_w:.0f} 0"
                          dur="{tick_dur}s" repeatCount="indefinite"/>
      </text>
    </g>
  </g>
  <rect x="{W-26}" y="328" width="9" height="13" fill="{CYAN}">
    <animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1s" repeatCount="indefinite"/>
  </rect>
</svg>
"""


# --------------------------------------------------------------- headers ----
def header(label, code, uid):
    W, H = 1000, 46
    tabw = 26 + len(label) * 10.6
    ticks = "".join(
        f'<rect x="{tabw + 34 + i*14}" y="26" width="6" height="2" fill="{LINE2}"/>'
        for i in range(int((W - tabw - 240) / 14))
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"
     font-family="{MONO}" role="img" aria-label="{label}">
{defs_common(W, H, uid)}
{backdrop(W, H, uid)}
  <path d="M0,0 L{tabw},0 L{tabw+16},{H} L0,{H} Z" fill="{CYAN}" fill-opacity="0.14"/>
  <path d="M0,0 L{tabw},0 L{tabw+16},{H} L0,{H} Z" fill="none" stroke="{CYAN}" stroke-opacity="0.55" stroke-width="1.4"/>
  <rect x="0" y="0" width="4" height="{H}" fill="{CYAN}"/>
  <text x="18" y="29" font-size="15" fill="{CYAN}" letter-spacing="3.2">{label}</text>
  <line x1="{tabw+28}" y1="{H/2}" x2="{W-150}" y2="{H/2}" stroke="{LINE}" stroke-width="1"/>
  {ticks}
  <text x="{W-136}" y="29" font-size="11.5" fill="{DIM}" letter-spacing="2">{code}</text>
  <rect x="0" y="{H-1.2}" width="{W}" height="1.2" fill="{LINE2}"/>
  <rect x="0" y="{H-1.2}" width="120" height="1.2" fill="{CYAN}">
    <animate attributeName="x" values="-120;{W};-120" dur="9s" repeatCount="indefinite"/>
  </rect>
</svg>
"""


# ----------------------------------------------------------------- stack ----
def stack():
    W = 1000
    groups = [
        ("LANGUAGES",   ["Go", "Rust", "Python", "TypeScript", "C#", "Bash", "PowerShell", "C++"]),
        ("CLOUD / IaC", ["Terraform", "Kubernetes", "Helm", "Docker", "Proxmox", "Cloudflare", "Nginx", "Linux"]),
        ("PLATFORM",    ["OpenTelemetry", "Grafana", "Prometheus", "PostgreSQL", "Redis", "GitHub Actions", "Ansible", "S3"]),
        ("FRONTEND",    ["Vue", "Astro", "Node.js", "Tailwind", "Electron", "Vite", "REST", "gRPC"]),
    ]
    rows = []
    y = 58
    for gi, (gname, items) in enumerate(groups):
        rows.append(f'<text x="30" y="{y+16}" font-size="12" fill="{CYAN}" letter-spacing="2.4">{gname}</text>')
        rows.append(f'<line x1="30" y1="{y+26}" x2="170" y2="{y+26}" stroke="{LINE}" stroke-width="1"/>')
        x = 196
        for ii, it in enumerate(items):
            w = 20 + len(it) * 8.2
            # Chips are always fully drawn — the panel must never read as empty
            # if a renderer drops SMIL or catches it mid-animation. The only
            # motion is the sweep highlight below.
            rows.append(
                f'<g>'
                f'<path d="M{x},{y} L{x+w},{y} L{x+w},{y+22} L{x+6},{y+22} L{x},{y+16} Z" '
                f'fill="{CYAN}" fill-opacity="0.07" stroke="{LINE2}" stroke-width="1"/>'
                f'<rect x="{x}" y="{y}" width="2.5" height="22" fill="{CYAN}" opacity="0.8">'
                f'<animate attributeName="opacity" values="0.8;1;0.8" dur="3s"'
                f' begin="{gi * 0.3 + ii * 0.08:.2f}s" repeatCount="indefinite"/>'
                f'</rect>'
                f'<text x="{x+11}" y="{y+15.5}" font-size="12" fill="{TEXT}">{it}</text>'
                f'</g>'
            )
            x += w + 9
        y += 44
    H = y + 22
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"
     font-family="{MONO}" role="img" aria-label="Technology stack">
{defs_common(W, H, "S")}
{backdrop(W, H, "S")}
  <rect x="1" y="1" width="{W-2}" height="{H-2}" fill="none" stroke="{LINE}" stroke-width="1.4"/>
{corners(10, 10, W-20, H-20, 18, CYAN, 1.8)}
  <text x="30" y="34" font-size="13" fill="{CYAN}" letter-spacing="3">&#9656; TOOLCHAIN MANIFEST</text>
  <text x="{W-190}" y="34" font-size="11" fill="{DIM}" letter-spacing="2">32 MODULES LOADED</text>
  <line x1="30" y1="44" x2="{W-30}" y2="44" stroke="{LINE}" stroke-width="1"/>
  {"".join(rows)}
  <g clip-path="url(#clipS)">
    <rect x="-160" y="0" width="160" height="{H}" fill="url(#glowS)" opacity="0.30">
      <animate attributeName="x" values="-160;{W};-160" dur="9s" repeatCount="indefinite"/>
    </rect>
  </g>
</svg>
"""


# ---------------------------------------------------------------- footer ----
def footer():
    W, H = 1000, 96
    bars = "".join(
        f'<rect x="{30 + i*13}" y="{62 - (i%7)*4 - 6}" width="6" height="{(i%7)*4 + 8}" fill="{CYAN}" opacity="{0.18 + (i%7)*0.09:.2f}">'
        f'<animate attributeName="height" values="{(i%7)*4+8};{((i+3)%7)*4+8};{(i%7)*4+8}" dur="{2.4 + (i%5)*0.4}s" repeatCount="indefinite"/>'
        f'<animate attributeName="y" values="{62-(i%7)*4-6};{62-((i+3)%7)*4-6};{62-(i%7)*4-6}" dur="{2.4 + (i%5)*0.4}s" repeatCount="indefinite"/>'
        f'</rect>'
        for i in range(26)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"
     font-family="{MONO}" role="img" aria-label="xfOS session footer">
{defs_common(W, H, "F")}
{backdrop(W, H, "F")}
  <rect x="1" y="1" width="{W-2}" height="{H-2}" fill="none" stroke="{LINE}" stroke-width="1.4"/>
  {bars}
  <text x="{W/2 + 90}" y="44" font-size="13" fill="{CYAN}" letter-spacing="3" text-anchor="middle">SESSION TERMINATED</text>
  <text x="{W/2 + 90}" y="66" font-size="11" fill="{DIM}" letter-spacing="1.8" text-anchor="middle">xfOS &#183; all traffic logged &#183; thanks for stopping by</text>
  <rect x="{W-40}" y="34" width="10" height="15" fill="{CYAN}">
    <animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1.05s" repeatCount="indefinite"/>
  </rect>
  <line x1="0" y1="{H-1}" x2="{W}" y2="{H-1}" stroke="{CYAN}" stroke-opacity="0.4" stroke-width="2"/>
</svg>
"""


HEADERS = [
    ("system-status",  "SYSTEM STATUS",     "SEC://0x01"),
    ("activity-log",   "ACTIVITY LOG",      "SEC://0x02"),
    ("code-analysis",  "CODE ANALYSIS",     "SEC://0x03"),
    ("assets",         "ASSETS RECOVERED",  "SEC://0x04"),
    ("toolchain",      "TOOLCHAIN",         "SEC://0x05"),
    ("network",        "NETWORK ACCESS",    "SEC://0x06"),
]

if __name__ == "__main__":
    (OUT / "banner.svg").write_text(banner())
    (OUT / "stack.svg").write_text(stack())
    (OUT / "footer.svg").write_text(footer())
    for i, (slug, label, code) in enumerate(HEADERS):
        (OUT / f"hdr-{slug}.svg").write_text(header(label, code, f"H{i}"))
    for p in sorted(OUT.iterdir()):
        print(f"{p.name:26} {p.stat().st_size:>8,} B")
