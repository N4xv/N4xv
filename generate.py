#!/usr/bin/env python3
"""
generate.py — N4xv profile card generator
Fetches live data → builds animated SVG → commits to repo
"""

import urllib.request
import urllib.parse
import json
import datetime
import math
import os

# ── helpers ──────────────────────────────────────────────────────────────────

def fetch(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "N4xv-profile/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  fetch error {url}: {e}")
        return {}

def fetch_text(url, timeout=8):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "N4xv-profile/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode()
    except Exception as e:
        print(f"  fetch_text error: {e}")
        return ""

# ── data fetching ─────────────────────────────────────────────────────────────

print("Fetching visitor IP location...")
geo = fetch("https://ipapi.co/json/")  # fallback to a fixed location if unavailable
if not geo.get("city"):
    geo = {"city": "Unknown", "country_name": "Earth", "latitude": 40.4, "longitude": -3.7,
           "timezone": "Europe/Madrid", "country_code": "ES"}

city        = geo.get("city", "Unknown")
country     = geo.get("country_name", "Earth")
country_code= geo.get("country_code", "??")
latitude    = float(geo.get("latitude", 40.4))
longitude   = float(geo.get("longitude", -3.7))
timezone    = geo.get("timezone", "Europe/Madrid")
print(f"  → {city}, {country} ({latitude}, {longitude})")

print("Fetching weather...")
wx_url = (f"https://api.open-meteo.com/v1/forecast"
          f"?latitude={latitude}&longitude={longitude}"
          f"&current=temperature_2m,weathercode,windspeed_10m,relative_humidity_2m"
          f"&timezone=auto")
wx = fetch(wx_url)
cur = wx.get("current", {})
temp_c      = cur.get("temperature_2m", "?")
wind_kmh    = cur.get("windspeed_10m", "?")
humidity    = cur.get("relative_humidity_2m", "?")
wcode       = cur.get("weathercode", 0)

WX_MAP = {
    0:  ("Clear sky",        "☀"),
    1:  ("Mainly clear",     "🌤"),
    2:  ("Partly cloudy",    "⛅"),
    3:  ("Overcast",         "☁"),
    45: ("Foggy",            "🌫"),
    48: ("Icy fog",          "🌫"),
    51: ("Light drizzle",    "🌦"),
    53: ("Drizzle",          "🌦"),
    55: ("Heavy drizzle",    "🌧"),
    61: ("Slight rain",      "🌧"),
    63: ("Rain",             "🌧"),
    65: ("Heavy rain",       "🌧"),
    71: ("Light snow",       "🌨"),
    73: ("Snow",             "❄"),
    75: ("Heavy snow",       "❄"),
    80: ("Rain showers",     "🌦"),
    81: ("Rain showers",     "🌦"),
    82: ("Violent showers",  "⛈"),
    95: ("Thunderstorm",     "⛈"),
    99: ("Thunderstorm",     "⛈"),
}
wx_desc, wx_icon = WX_MAP.get(wcode, ("Unknown", "?"))
print(f"  → {temp_c}°C, {wx_desc}, wind {wind_kmh} km/h, humidity {humidity}%")

print("Fetching GitHub stats...")
GITHUB_USER = "N4xv"
gh_token = os.environ.get("GH_TOKEN", "")
gh_headers = {"User-Agent": "N4xv-profile/1.0"}
if gh_token:
    gh_headers["Authorization"] = f"token {gh_token}"

def gh_fetch(path):
    try:
        req = urllib.request.Request(
            f"https://api.github.com{path}", headers=gh_headers)
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print(f"  gh error {path}: {e}")
        return {}

user_data  = gh_fetch(f"/users/{GITHUB_USER}")
repos_data = gh_fetch(f"/users/{GITHUB_USER}/repos?per_page=100&sort=updated")

public_repos = user_data.get("public_repos", 0)
followers    = user_data.get("followers", 0)
following    = user_data.get("following", 0)
total_stars  = sum(r.get("stargazers_count", 0) for r in repos_data) if isinstance(repos_data, list) else 0
top_langs    = {}
if isinstance(repos_data, list):
    for r in repos_data:
        lang = r.get("language")
        if lang:
            top_langs[lang] = top_langs.get(lang, 0) + 1
top_lang = max(top_langs, key=top_langs.get) if top_langs else "Python"
print(f"  → repos:{public_repos} stars:{total_stars} followers:{followers} top:{top_lang}")

print("Fetching WakaTime... (skipped — no key)")
# WakaTime would go here if API key is set

# ── time ──────────────────────────────────────────────────────────────────────
now_utc = datetime.datetime.utcnow()

# Rough UTC offset from timezone name (good enough without pytz)
TZ_OFFSETS = {
    "Europe/Madrid": 1, "Europe/London": 0, "Europe/Paris": 1,
    "America/New_York": -5, "America/Los_Angeles": -8, "America/Chicago": -6,
    "Asia/Tokyo": 9, "Asia/Shanghai": 8, "Asia/Kolkata": 5,
    "Australia/Sydney": 10, "America/Sao_Paulo": -3,
}
tz_offset = TZ_OFFSETS.get(timezone, 0)
if now_utc.month in range(3, 11):  # rough DST
    tz_offset += 1
local_dt  = now_utc + datetime.timedelta(hours=tz_offset)
local_time_str = local_dt.strftime("%H:%M")
local_date_str = local_dt.strftime("%a, %d %b %Y")
utc_str        = now_utc.strftime("%H:%M UTC")
print(f"  → local time of visitor: {local_time_str} ({timezone})")

# Hour-based greeting
h = local_dt.hour
if   5  <= h < 12: greeting = "good morning"
elif 12 <= h < 18: greeting = "good afternoon"
elif 18 <= h < 22: greeting = "good evening"
else:              greeting = "up late?"

# ── SVG generation ────────────────────────────────────────────────────────────
print("Generating SVG...")

# Sanitize strings for SVG
def s(v):
    return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

# Temperature color
def temp_color(t):
    try:
        t = float(t)
        if t <= 0:   return "#79c0ff"
        if t <= 10:  return "#a5d6ff"
        if t <= 20:  return "#7ee787"
        if t <= 28:  return "#ffa657"
        return "#ff7b72"
    except: return "#8b949e"

tc = temp_color(temp_c)

# Build mini bar chart for top languages
lang_items = sorted(top_langs.items(), key=lambda x: -x[1])[:5]
lang_total = sum(v for _, v in lang_items) or 1
LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#F7DF1E", "TypeScript": "#2b7489",
    "Go": "#00ADD8", "Java": "#b07219", "Rust": "#dea584",
    "Bash": "#89e051", "Shell": "#89e051", "HTML": "#e34c26",
    "CSS": "#563d7c", "C": "#555555", "C++": "#f34b7d",
}
LANG_TEXT_COLORS = {
    "Python": "#3572A5", "JavaScript": "#d4a017", "TypeScript": "#2b7489",
    "Go": "#00ADD8", "Java": "#b07219", "Rust": "#dea584",
    "Bash": "#3fb950", "Shell": "#3fb950", "HTML": "#ff7b72",
    "CSS": "#d2a8ff", "C": "#8b949e", "C++": "#ff7b72",
}

def lang_bar_svg():
    out = []
    x = 0
    W = 320
    for lang, count in lang_items:
        w = round((count / lang_total) * W)
        col = LANG_COLORS.get(lang, "#8b949e")
        out.append(f'<rect x="{x}" y="0" width="{w}" height="6" fill="{col}" rx="1"/>')
        x += w + 1
    return "".join(out)

def lang_labels_svg():
    out = []
    for i, (lang, count) in enumerate(lang_items):
        col = LANG_TEXT_COLORS.get(lang, "#8b949e")
        pct = round((count / lang_total) * 100)
        x = 490 + (i % 3) * 115
        y = 390 + (i // 3) * 16
        dot_col = LANG_COLORS.get(lang, "#8b949e")
        out.append(f'<circle cx="{x}" cy="{y-4}" r="3" fill="{dot_col}"/>')
        out.append(f'<text x="{x+8}" y="{y}" class="mono" font-size="10" fill="{col}">{s(lang)} <tspan fill="#30363d">{pct}%</tspan></text>')
    return "".join(out)

svg = f'''<svg width="900" height="520" viewBox="0 0 900 520" xmlns="http://www.w3.org/2000/svg">
<defs>
  <style>
    .mono {{ font-family: "JetBrains Mono",ui-monospace,"Cascadia Code","Fira Code",Consolas,monospace; }}
    .kw   {{ fill: #ff7b72; }}
    .fn   {{ fill: #d2a8ff; }}
    .str  {{ fill: #a5d6ff; }}
    .num  {{ fill: #79c0ff; }}
    .cmt  {{ fill: #484f58; font-style: italic; }}
    .var  {{ fill: #ffa657; }}
    .pun  {{ fill: #c9d1d9; }}
    .dim  {{ fill: #21262d; }}
    .mute {{ fill: #484f58; }}
    .lnum {{ fill: #30363d; }}
    .wht  {{ fill: #f0f6fc; }}
  </style>
  <filter id="glow">
    <feGaussianBlur stdDeviation="3" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <filter id="gs">
    <feGaussianBlur stdDeviation="1.5" result="b"/>
    <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
  <clipPath id="rp"><rect x="450" y="0" width="450" height="330"/></clipPath>
  <clipPath id="all"><rect width="900" height="520"/></clipPath>
</defs>

<g clip-path="url(#all)">

<!-- BG -->
<rect width="900" height="520" fill="#0d1117"/>

<!-- top accent -->
<line x1="0" y1="0" x2="900" y2="0" stroke="#1f6feb" stroke-width="2.5"/>

<!-- dot grid -->
<g fill="#161b22" opacity="0.9">
{"".join(f'<circle cx="{x}" cy="{y}" r="0.7"/>' for y in range(30,330,30) for x in range(30,900,30))}
</g>

<!-- vertical divider -->
<line x1="450" y1="20" x2="450" y2="330" stroke="#21262d" stroke-width="1"/>
<line x1="450" y1="20" x2="450" y2="330" stroke="#1f6feb" stroke-width="0.4" opacity="0.5"/>

<!-- ── corner brackets ── -->
<g fill="none" stroke="#21262d" stroke-width="1.2">
  <path d="M 22 22 L 22 42 M 22 22 L 42 22"/>
  <path d="M 428 308 L 428 288 M 428 308 L 408 308"/>
</g>
<g fill="none" stroke="#58a6ff" stroke-width="1.5" filter="url(#gs)">
  <path d="M 22 22 L 22 32 M 22 22 L 32 22">
    <animate attributeName="opacity" values="0.4;1;0.4" dur="2.5s" repeatCount="indefinite"/>
  </path>
  <path d="M 428 308 L 428 298 M 428 308 L 418 308">
    <animate attributeName="opacity" values="0.4;1;0.4" dur="2.5s" begin="1.2s" repeatCount="indefinite"/>
  </path>
</g>

<!-- ══ LEFT PANEL ══ -->

<!-- name -->
<text x="225" y="115" class="mono wht" font-size="58" font-weight="700"
      text-anchor="middle" letter-spacing="-1" filter="url(#glow)">N4xv</text>
<rect x="342" y="68" width="4" height="52" fill="#58a6ff" filter="url(#gs)">
  <animate attributeName="opacity" values="1;1;0;0" dur="1.1s" repeatCount="indefinite"/>
</rect>

<!-- subtitle -->
<text x="225" y="143" class="mono" font-size="11" text-anchor="middle"
      fill="#484f58" letter-spacing="4">DEV · SECURITY · BUILDER</text>

<!-- divider under title -->
<line x1="70" y1="157" x2="380" y2="157" stroke="#21262d" stroke-width="0.8"/>

<!-- ── LIVE VISITOR DATA ── -->
<!-- greeting -->
<text x="90" y="182" class="mono" font-size="11" fill="#30363d">// visitor</text>

<text x="90" y="200" class="mono" font-size="12">
  <tspan fill="#484f58">greeting  </tspan><tspan fill="#7ee787">{s(greeting)}, visitor</tspan>
</text>
<text x="90" y="216" class="mono" font-size="12">
  <tspan fill="#484f58">location  </tspan><tspan fill="#a5d6ff">{s(city)}, {s(country)}</tspan>
</text>
<text x="90" y="232" class="mono" font-size="12">
  <tspan fill="#484f58">local time </tspan><tspan fill="#ffa657">{s(local_time_str)}</tspan>
  <tspan fill="#30363d"> ({s(utc_str)})</tspan>
</text>
<text x="90" y="248" class="mono" font-size="12">
  <tspan fill="#484f58">date      </tspan><tspan fill="#8b949e">{s(local_date_str)}</tspan>
</text>

<!-- weather line -->
<text x="90" y="268" class="mono" font-size="11" fill="#30363d">// weather</text>
<text x="90" y="285" class="mono" font-size="12">
  <tspan fill="#484f58">temp      </tspan><tspan fill="{tc}">{s(temp_c)}°C</tspan>
  <tspan fill="#30363d">  —  </tspan><tspan fill="#8b949e">{s(wx_desc)}</tspan>
</text>
<text x="90" y="301" class="mono" font-size="12">
  <tspan fill="#484f58">wind      </tspan><tspan fill="#8b949e">{s(wind_kmh)} km/h</tspan>
  <tspan fill="#30363d">  humidity </tspan><tspan fill="#8b949e">{s(humidity)}%</tspan>
</text>

<!-- ══ RIGHT PANEL — code editor ══ -->
<g clip-path="url(#rp)">
  <!-- chrome bar -->
  <rect x="450" y="0" width="450" height="22" fill="#161b22"/>
  <circle cx="466" cy="11" r="4" fill="#ff5f57"/>
  <circle cx="480" cy="11" r="4" fill="#febc2e"/>
  <circle cx="494" cy="11" r="4" fill="#28c840"/>
  <text x="520" y="15" class="mono" font-size="10" fill="#484f58">profile.py — N4xv</text>

  <!-- gutter + code bg -->
  <rect x="450" y="22" width="32" height="308" fill="#0d1117"/>
  <rect x="482" y="22" width="418" height="308" fill="#0d1117"/>

  <!-- active line -->
  <rect x="450" y="106" width="450" height="13" fill="#161b22">
    <animate attributeName="y"
      values="106;120;134;148;162;176;190;176;162;148;134;120;106"
      dur="9s" repeatCount="indefinite"/>
  </rect>

  <!-- line numbers -->
  <g class="mono lnum" font-size="10" text-anchor="end">
    {"".join(f'<text x="476" y="{34 + i*14}">{str(i+1).rjust(2)}</text>' for i in range(21))}
  </g>

  <!-- code — typed in -->
  <g class="mono" font-size="11">

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="0.1s" fill="freeze"/>
    <text x="490" y="34"><tspan class="kw">class </tspan><tspan class="fn">N4xv</tspan><tspan class="pun">:</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="0.35s" fill="freeze"/>
    <text x="490" y="62"><tspan fill="#30363d">  </tspan><tspan class="kw">def </tspan><tspan class="fn">__init__</tspan><tspan class="pun">(</tspan><tspan class="var">self</tspan><tspan class="pun">):</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="0.6s" fill="freeze"/>
    <text x="490" y="76"><tspan fill="#30363d">    </tspan><tspan class="var">self</tspan><tspan class="pun">.</tspan><tspan class="str">age</tspan><tspan class="pun">   = </tspan><tspan class="num">19</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="0.85s" fill="freeze"/>
    <text x="490" y="90"><tspan fill="#30363d">    </tspan><tspan class="var">self</tspan><tspan class="pun">.</tspan><tspan class="str">role</tspan><tspan class="pun">  = [</tspan><tspan class="str">"dev"</tspan><tspan class="pun">, </tspan><tspan class="str">"security"</tspan><tspan class="pun">, </tspan><tspan class="str">"builder"</tspan><tspan class="pun">]</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="1.1s" fill="freeze"/>
    <text x="490" y="104"><tspan fill="#30363d">    </tspan><tspan class="var">self</tspan><tspan class="pun">.</tspan><tspan class="str">stack</tspan><tspan class="pun"> = [</tspan><tspan class="str">"py"</tspan><tspan class="pun">, </tspan><tspan class="str">"ts"</tspan><tspan class="pun">, </tspan><tspan class="str">"go"</tspan><tspan class="pun">, </tspan><tspan class="str">"java"</tspan><tspan class="pun">]</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="1.35s" fill="freeze"/>
    <text x="490" y="132"><tspan fill="#30363d">  </tspan><tspan class="kw">def </tspan><tspan class="fn">mindset</tspan><tspan class="pun">(</tspan><tspan class="var">self</tspan><tspan class="pun">):</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="1.6s" fill="freeze"/>
    <text x="490" y="146"><tspan fill="#30363d">    </tspan><tspan class="kw">return </tspan><tspan class="str">"break → read → build"</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="1.85s" fill="freeze"/>
    <text x="490" y="174"><tspan fill="#30363d">  </tspan><tspan class="kw">def </tspan><tspan class="fn">status</tspan><tspan class="pun">(</tspan><tspan class="var">self</tspan><tspan class="pun">):</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="2.1s" fill="freeze"/>
    <text x="490" y="188"><tspan fill="#30363d">    </tspan><tspan class="cmt"># always learning. always shipping.</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="2.35s" fill="freeze"/>
    <text x="490" y="202"><tspan fill="#30363d">    </tspan><tspan class="kw">return </tspan><tspan class="num">True</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="2.6s" fill="freeze"/>
    <text x="490" y="230"><tspan class="fn">me</tspan><tspan class="pun"> = </tspan><tspan class="fn">N4xv</tspan><tspan class="pun">()</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="2.85s" fill="freeze"/>
    <text x="490" y="244"><tspan class="kw">assert </tspan><tspan class="fn">me</tspan><tspan class="pun">.</tspan><tspan class="fn">status</tspan><tspan class="pun">() == </tspan><tspan class="num">True</tspan><tspan class="cmt">  # ✓ passes</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="3.1s" fill="freeze"/>
    <text x="490" y="272"><tspan class="cmt"># 19. no degree. just obsession.</tspan></text></g>

    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="3.35s" fill="freeze"/>
    <text x="490" y="286"><tspan class="cmt"># ship → break → understand → repeat</tspan></text></g>

    <!-- cursor -->
    <g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.01s" begin="3.6s" fill="freeze"/>
    <rect x="490" y="292" width="7" height="12" fill="#58a6ff">
      <animate attributeName="opacity" values="1;1;0;0" dur="1.1s" begin="3.6s" repeatCount="indefinite"/>
    </rect></g>

  </g>

  <!-- status bar -->
  <rect x="450" y="316" width="450" height="14" fill="#161b22"/>
  <line x1="450" y1="316" x2="900" y2="316" stroke="#21262d" stroke-width="0.8"/>
  <text x="460" y="327" class="mono" font-size="9" fill="#58a6ff">● N4xv</text>
  <text x="500" y="327" class="mono" font-size="9" fill="#484f58">main</text>
  <text x="530" y="327" class="mono" font-size="9" fill="#484f58">Python 3.12</text>
  <text x="680" y="327" class="mono" font-size="9" fill="#484f58">{s(city)}, {s(country_code)}</text>
  <text x="760" y="327" class="mono" font-size="9" fill="#484f58">{s(local_time_str)}</text>
  <text x="800" y="327" class="mono" font-size="9" fill="#484f58">UTF-8</text>
  <text x="840" y="327" class="mono" font-size="9" fill="#1f6feb">⬡ sec</text>
</g>

<!-- ══ BOTTOM DARK BAND ══ -->
<rect x="0" y="330" width="900" height="190" fill="#010409"/>
<line x1="0" y1="330" x2="900" y2="330" stroke="#21262d" stroke-width="0.8"/>

<!-- github stats section -->
<text x="50" y="360" class="mono" font-size="10" fill="#30363d">// github.stats</text>

<!-- stat boxes -->
<g class="mono">
  <!-- repos -->
  <rect x="50"  y="370" width="90" height="44" rx="4" fill="#0d1117" stroke="#21262d" stroke-width="0.8"/>
  <text x="95"  y="390" font-size="20" font-weight="700" fill="#f0f6fc" text-anchor="middle">{s(public_repos)}</text>
  <text x="95"  y="406" font-size="9"  fill="#484f58" text-anchor="middle">repos</text>

  <!-- stars -->
  <rect x="150" y="370" width="90" height="44" rx="4" fill="#0d1117" stroke="#21262d" stroke-width="0.8"/>
  <text x="195" y="390" font-size="20" font-weight="700" fill="#ffa657" text-anchor="middle">{s(total_stars)}</text>
  <text x="195" y="406" font-size="9"  fill="#484f58" text-anchor="middle">stars</text>

  <!-- followers -->
  <rect x="250" y="370" width="90" height="44" rx="4" fill="#0d1117" stroke="#21262d" stroke-width="0.8"/>
  <text x="295" y="390" font-size="20" font-weight="700" fill="#58a6ff" text-anchor="middle">{s(followers)}</text>
  <text x="295" y="406" font-size="9"  fill="#484f58" text-anchor="middle">followers</text>

  <!-- top lang -->
  <rect x="350" y="370" width="90" height="44" rx="4" fill="#0d1117" stroke="#21262d" stroke-width="0.8"/>
  <text x="395" y="390" font-size="13" font-weight="700" fill="#d2a8ff" text-anchor="middle">{s(top_lang[:8])}</text>
  <text x="395" y="406" font-size="9"  fill="#484f58" text-anchor="middle">top lang</text>
</g>

<!-- language bar -->
<text x="50" y="435" class="mono" font-size="10" fill="#30363d">// languages</text>
<g transform="translate(50, 444)">{lang_bar_svg()}</g>
{lang_labels_svg()}

<!-- col 2: currently -->
<line x1="460" y1="345" x2="460" y2="510" stroke="#161b22" stroke-width="1"/>

<text x="490" y="360" class="mono" font-size="10" fill="#30363d">// currently</text>
<text x="490" y="378" class="mono" font-size="11"><tspan fill="#484f58">learning   </tspan><tspan fill="#a5d6ff">Go · Web Exploitation</tspan></text>
<text x="490" y="394" class="mono" font-size="11"><tspan fill="#484f58">building   </tspan><tspan fill="#a5d6ff">tools I needed and didn't exist</tspan></text>
<text x="490" y="410" class="mono" font-size="11"><tspan fill="#484f58">exploring  </tspan><tspan fill="#a5d6ff">CTF challenges</tspan></text>

<text x="490" y="432" class="mono" font-size="10" fill="#30363d">// stack</text>
<text x="490" y="450" class="mono" font-size="11"><tspan fill="#484f58">security   </tspan><tspan fill="#ff7b72">burp · kali · owasp · recon</tspan></text>
<text x="490" y="466" class="mono" font-size="11"><tspan fill="#484f58">frontend   </tspan><tspan fill="#d2a8ff">react · html · css · ts</tspan></text>
<text x="490" y="482" class="mono" font-size="11"><tspan fill="#484f58">tools      </tspan><tspan fill="#8b949e">linux · docker · git · vim</tspan></text>

<!-- bottom rule + credit -->
<line x1="40" y1="505" x2="860" y2="505" stroke="#161b22" stroke-width="0.8"/>
<text x="450" y="517" class="mono" font-size="9" fill="#21262d" text-anchor="middle">
  generated {s(now_utc.strftime("%Y-%m-%d %H:%M"))} UTC · data: open-meteo.com · ipapi.co · github.com
</text>

<!-- scan line -->
<line x1="0" y1="0" x2="900" y2="0" stroke="#58a6ff" stroke-width="0.5" opacity="0">
  <animate attributeName="y1" values="0;520" dur="5s" repeatCount="indefinite"/>
  <animate attributeName="y2" values="0;520" dur="5s" repeatCount="indefinite"/>
  <animate attributeName="opacity" values="0;0.35;0.35;0" keyTimes="0;0.02;0.98;1" dur="5s" repeatCount="indefinite"/>
</line>

</g>
</svg>'''

with open("hero.svg", "w", encoding="utf-8") as f:
    f.write(svg)

print(f"hero.svg written ({len(svg):,} chars)")
