#!/usr/bin/env python3
"""
Shorty D — Page Editor (Manage Me Integration)
----------------------------------------------
Manage your public link hub directly from Manage Me:
  1. Latest Drop: artwork, title, subtitle, and 2 action buttons (Spotify, Apple, YouTube, etc.)
  2. Booking & Press Email
  3. Platforms shown in the center orbit (Spotify, Apple Music, YouTube, Instagram, TikTok)
  4. One-click Save & Publish straight to GitHub Pages.
"""

import http.server
import io
import json
import os
import re
import socketserver
import subprocess
import time
import webbrowser
from html import escape
from pathlib import Path

try:
    from PIL import Image, ImageOps
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")
ASSETS = os.path.join(HERE, "assets")
DROP_COVER_FILE = "assets/no-days-off-cover.jpg"
PORT = 7440
LIVE_URL = "https://itsshortyd.github.io/shortyd-links/"
PUBLISH_FILES = ["index.html", DROP_COVER_FILE, "assets/shortyd-logo.png"]


# ---------------------------------------------------------------- helpers ----
def read_index():
    with open(INDEX, "r", encoding="utf-8") as f:
        return f.read()


def write_index(text):
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(text)


def bump_cache_version(asset_path):
    """
    Add/refresh a ?v=<timestamp> on every reference to this asset so the
    live site shows the new image immediately instead of a cached one.
    """
    html = read_index()
    stamp = str(int(time.time()))
    base = re.escape(asset_path)
    html = re.sub(base + r'(?:\?v=\d+)?', asset_path + "?v=" + stamp, html)
    write_index(html)


def save_image(raw_bytes, dest_filename):
    """Normalize an uploaded image to a clean JPEG at the fixed filename."""
    dest = os.path.join(HERE, dest_filename)
    if HAVE_PIL:
        try:
            img = Image.open(io.BytesIO(raw_bytes))
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((1600, 1600))
            img.save(dest, "JPEG", quality=88, optimize=True)
            return
        except Exception:
            pass
    with open(dest, "wb") as f:
        f.write(raw_bytes)


def parse_multipart(body, boundary):
    """Minimal multipart/form-data parser (fields + file uploads)."""
    parts = body.split(b"--" + boundary)
    fields, files = {}, {}
    for part in parts:
        if not part or part in (b"--\r\n", b"--", b"\r\n"):
            continue
        if b"\r\n\r\n" not in part:
            continue
        header_blob, data = part.split(b"\r\n\r\n", 1)
        data = data.rstrip(b"\r\n")
        headers = header_blob.decode("utf-8", "ignore")
        name_m = re.search(r'name="([^"]+)"', headers)
        if not name_m:
            continue
        name = name_m.group(1)
        if "filename=" in headers:
            fn = re.search(r'filename="([^"]*)"', headers).group(1)
            if fn and data:
                files[name] = data
        else:
            fields[name] = data.decode("utf-8", "ignore")
    return fields, files


def git_publish():
    """Commit and push. Returns (ok, message)."""
    try:
        subprocess.run(["git", "-C", HERE, "add", "--"] + PUBLISH_FILES,
                       check=True, capture_output=True)
        staged = subprocess.run(
            ["git", "-C", HERE, "diff", "--cached", "--name-only", "--"] + PUBLISH_FILES,
            capture_output=True, text=True).stdout.strip()
        if not staged:
            return True, "No changes to publish — everything was already up to date."
        subprocess.run(
            ["git", "-C", HERE, "commit", "-m", "Update site via Manage Me", "--"] + PUBLISH_FILES,
            check=True, capture_output=True)
        push = subprocess.run(["git", "-C", HERE, "push", "origin", "main"],
                              capture_output=True, text=True)
        if push.returncode != 0:
            return False, "Saved locally, but publish failed:\n" + push.stderr.strip()
        return True, "Published! Your live page will update in a minute or two."
    except subprocess.CalledProcessError as e:
        return False, "Git error:\n" + (e.stderr.decode() if e.stderr else str(e))


def extract_site_data():
    """Extract all editable settings from index.html."""
    html = read_index()
    data = {}

    # Drop Title & Subtitle
    m = re.search(r'id="dropTitle">(.*?)</h2>', html, re.S)
    data["drop_title"] = m.group(1).strip() if m else "NO DAYS OFF"

    m = re.search(r'id="dropSubtitle">(.*?)</p>', html, re.S)
    data["drop_subtitle"] = m.group(1).strip() if m else "Single • Available on all platforms"

    # Button 1
    m = re.search(r'id="dropBtn1Text">(.*?)</span>', html, re.S)
    data["btn1_text"] = m.group(1).strip() if m else "Spotify"

    m = re.search(r'id="dropBtn1"[^>]*href="([^"]+)"|href="([^"]+)"[^>]*id="dropBtn1"', html, re.S)
    data["btn1_url"] = (m.group(1) or m.group(2)).strip() if m else ""

    # Button 2
    m = re.search(r'id="dropBtn2Text">(.*?)</span>', html, re.S)
    data["btn2_text"] = m.group(1).strip() if m else "Apple Music"

    m = re.search(r'id="dropBtn2"[^>]*href="([^"]+)"|href="([^"]+)"[^>]*id="dropBtn2"', html, re.S)
    data["btn2_url"] = (m.group(1) or m.group(2)).strip() if m else ""

    # Booking Email
    m = re.search(r'id="bookingEmailText">(.*?)</span>', html, re.S)
    data["booking_email"] = m.group(1).strip() if m else "booking@meeshortyd.site"

    # Orbit Platforms
    platforms = [
        ("spotify", "orbitSpotify"),
        ("applemusic", "orbitApple"),
        ("youtube", "orbitYouTube"),
        ("instagram", "orbitInstagram"),
        ("tiktok", "orbitTikTok")
    ]
    for key, pid in platforms:
        m = re.search(r'id="' + pid + r'"[^>]*href="([^"]+)"|href="([^"]+)"[^>]*id="' + pid + r'"', html, re.S)
        url = (m.group(1) or m.group(2)).strip() if m else ""
        
        # Check if hidden
        tag_m = re.search(r'<a[^>]*id="' + pid + r'"[^>]*>', html)
        is_shown = True
        if tag_m and "display:none" in tag_m.group(0):
            is_shown = False
            
        data[f"{key}_url"] = url
        data[f"{key}_show"] = is_shown

    return data


def save_site_data(fields, files):
    """Save all form fields and uploaded artwork into index.html."""
    html = read_index()

    # Drop Artwork
    if "drop_cover" in files and files["drop_cover"]:
        save_image(files["drop_cover"], DROP_COVER_FILE)
        bump_cache_version(DROP_COVER_FILE)
        html = read_index()

    # Drop Title
    title = fields.get("drop_title", "").strip()
    if title:
        safe_title = escape(title)
        html = re.sub(r'(id="dropTitle">).*?(</h2>)', r'\g<1>' + safe_title + r'\g<2>', html)
        html = re.sub(r'(id="platformLabel">).*?(</p>)', r'\g<1>NEWEST DROP — "' + safe_title + r'"\g<2>', html)

    # Drop Subtitle
    sub = fields.get("drop_subtitle", "").strip()
    if sub:
        html = re.sub(r'(id="dropSubtitle">).*?(</p>)', r'\g<1>' + escape(sub) + r'\g<2>', html)

    # Button 1
    b1_text = fields.get("btn1_text", "").strip()
    b1_url = fields.get("btn1_url", "").strip()
    if b1_text:
        html = re.sub(r'(id="dropBtn1Text">).*?(</span>)', r'\g<1>' + escape(b1_text) + r'\g<2>', html)
    if b1_url:
        html = re.sub(r'(<a\s+[^>]*id="dropBtn1"[^>]*href=")[^"]*(")', r'\g<1>' + escape(b1_url) + r'\g<2>', html)
        html = re.sub(r'(<a\s+[^>]*href=")[^"]*("[^>]*id="dropBtn1")', r'\g<1>' + escape(b1_url) + r'\g<2>', html)

    # Button 2
    b2_text = fields.get("btn2_text", "").strip()
    b2_url = fields.get("btn2_url", "").strip()
    if b2_text:
        html = re.sub(r'(id="dropBtn2Text">).*?(</span>)', r'\g<1>' + escape(b2_text) + r'\g<2>', html)
    if b2_url:
        html = re.sub(r'(<a\s+[^>]*id="dropBtn2"[^>]*href=")[^"]*(")', r'\g<1>' + escape(b2_url) + r'\g<2>', html)
        html = re.sub(r'(<a\s+[^>]*href=")[^"]*("[^>]*id="dropBtn2")', r'\g<1>' + escape(b2_url) + r'\g<2>', html)

    # Booking Email
    email = fields.get("booking_email", "").strip()
    if email:
        safe_email = escape(email)
        html = re.sub(r'(id="bookingEmailText">).*?(</span>)', r'\g<1>' + safe_email + r'\g<2>', html)
        html = re.sub(r'(id="bookingLink"[^>]*href="mailto:)[^"]*(")', r'\g<1>' + safe_email + r'\g<2>', html)
        html = re.sub(r'(href="mailto:)[^"]*("[^>]*id="bookingLink")', r'\g<1>' + safe_email + r'\g<2>', html)

    # Orbit Platforms
    platforms = [
        ("spotify", "orbitSpotify"),
        ("applemusic", "orbitApple"),
        ("youtube", "orbitYouTube"),
        ("instagram", "orbitInstagram"),
        ("tiktok", "orbitTikTok")
    ]
    for key, pid in platforms:
        url = fields.get(f"{key}_url", "").strip()
        show = (f"{key}_show" in fields)
        if url:
            html = re.sub(r'(<a\s+[^>]*id="' + pid + r'"[^>]*href=")[^"]*(")', r'\g<1>' + escape(url) + r'\g<2>', html)
            html = re.sub(r'(<a\s+[^>]*href=")[^"]*("[^>]*id="' + pid + r'")', r'\g<1>' + escape(url) + r'\g<2>', html)

        def toggle_display(m):
            tag = m.group(0)
            if not show:
                if 'display:none' not in tag:
                    tag = re.sub(r'style="', 'style="display:none; ', tag)
            else:
                tag = re.sub(r'display:none;\s*', '', tag)
            return tag

        html = re.sub(r'<a\s+[^>]*id="' + pid + r'"[^>]*>', toggle_display, html)

    write_index(html)


# ------------------------------------------------------------------- page ----
def editor_page():
    data = extract_site_data()
    cb = int(time.time())

    def checked(val):
        return 'checked' if val else ''

    return f"""<!DOCTYPE html>
<html lang="en" class="mm" data-area="site"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Site · Manage Me</title>
<link rel="stylesheet" href="/ui/mm.css">
<script src="/ui/mm.js"></script>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--mm-bg, #0e0f12); color: var(--mm-text, #f1f1f3);
         font-family: var(--mm-font, -apple-system, system-ui, sans-serif); }}
  .wrap {{ max-width: 1080px; padding: 24px; margin: 0 auto; }}
  .site-grid {{ display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 24px; align-items: start; }}
  .card {{ margin-bottom: 20px; }}
  .row {{ display: flex; gap: 18px; align-items: center; }}
  .thumb {{ background: #101115; border: 1px solid var(--mm-line-2, #2a2c33); border-radius: 12px;
           overflow: hidden; flex: 0 0 auto; width: 96px; height: 96px; }}
  .thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .pick {{ flex: 1; min-width: 0; }}
  .pick label.mm-btn {{ cursor: pointer; }}
  .pick input[type=file] {{ position: absolute; width: 1px; height: 1px; opacity: 0; }}
  .fname {{ display: block; margin-top: 8px; font-size: 12px; color: var(--mm-dim, #6c707a); }}
  
  .form-group {{ margin-bottom: 14px; }}
  .form-group label {{ display: block; font-size: 12px; font-weight: 600; text-transform: uppercase;
                      letter-spacing: 0.5px; color: var(--mm-muted, #a3a7b0); margin-bottom: 6px; }}
  input[type=text], input[type=email] {{
    width: 100%; font-size: 14px; padding: 10px 14px; border-radius: 8px;
    background: #14161f; border: 1px solid var(--mm-line-2, #2a2c33); color: #fff;
  }}
  .input-grid {{ display: grid; grid-template-columns: 140px 1fr; gap: 10px; }}
  
  .platform-row {{
    display: flex; align-items: center; gap: 12px; padding: 10px 12px;
    border-radius: 8px; background: rgba(255,255,255,0.02); margin-bottom: 8px;
    border: 1px solid rgba(255,255,255,0.05);
  }}
  .platform-row input[type=checkbox] {{ width: 18px; height: 18px; cursor: pointer; }}
  .platform-name {{ width: 100px; font-weight: 600; font-size: 13px; }}
  .platform-input {{ flex: 1; }}

  .note {{ color: var(--mm-muted, #a3a7b0); font-size: 12px; margin: 6px 0 0; line-height: 1.4; }}
  .side .mm-card {{ position: sticky; top: 20px; }}
  .side p {{ color: var(--mm-muted, #a3a7b0); font-size: 13px; line-height: 1.55; margin: 0 0 14px; }}
  #status {{ margin-top: 12px; padding: 12px 14px; border-radius: 12px; font-size: 13px;
            white-space: pre-wrap; display: none; border: 1px solid var(--mm-line-2, #2a2c33);
            background: var(--mm-surface-2, #1d1f25); border-left-width: 3px; }}
  #status.ok {{ display: block; border-left-color: var(--mm-green, #4cc98a); }}
  #status.err {{ display: block; border-left-color: var(--mm-red, #f0625a); }}
  #status.busy {{ display: block; border-left-color: var(--mm-amber, #f2b33d); }}
  a {{ color: var(--mm-text, #f1f1f3); }}
  @media (max-width: 860px) {{ .site-grid {{ grid-template-columns: 1fr; }} }}
</style></head>
<body><div class="mm-page wrap">
  <div class="mm-head">
    <div class="mm-head-text">
      <div class="mm-kicker">MANAGE ME &bull; SITE</div>
      <h1 class="mm-title" style="margin:4px 0;">Site &amp; Link Hub</h1>
      <p class="mm-sub">Update your latest drop, change streaming buttons, customize booking email, and toggle orbit sites.</p>
    </div>
    <div class="mm-actions"><a class="mm-btn ghost" href="{LIVE_URL}" target="_blank">View Live Page ↗</a></div>
  </div>

  <form id="f" class="mm-form site-grid">
   <div>
    <!-- Section 1: Latest Drop -->
    <div class="mm-card card">
      <div class="mm-card-title" style="font-size:16px; font-weight:700; margin-bottom:14px; color:#ffcc33;">🎵 Latest Drop</div>
      
      <div class="form-group">
        <label>Drop Artwork / Cover</label>
        <div class="row">
          <div class="thumb"><img id="dc" src="{DROP_COVER_FILE}?v={cb}"></div>
          <div class="pick">
            <label class="mm-btn">Upload New Cover<input type="file" name="drop_cover" accept="image/*" onchange="prev(this,'dc')"></label>
            <span class="fname" id="dc-name">Square artwork or video thumbnail.</span>
          </div>
        </div>
      </div>

      <div class="form-group">
        <label>Drop Title</label>
        <input type="text" name="drop_title" value="{escape(data['drop_title'])}" placeholder="e.g. NO DAYS OFF or FEIN FOR YOUR LOVE">
      </div>

      <div class="form-group">
        <label>Drop Subtitle / Description</label>
        <input type="text" name="drop_subtitle" value="{escape(data['drop_subtitle'])}" placeholder="e.g. Single • Available on all platforms">
      </div>

      <div class="form-group">
        <label>Button 1 (Label &amp; Link)</label>
        <div class="input-grid">
          <input type="text" name="btn1_text" value="{escape(data['btn1_text'])}" placeholder="Spotify">
          <input type="text" name="btn1_url" value="{escape(data['btn1_url'])}" placeholder="https://open.spotify.com/artist/...">
        </div>
      </div>

      <div class="form-group">
        <label>Button 2 (Label &amp; Link)</label>
        <div class="input-grid">
          <input type="text" name="btn2_text" value="{escape(data['btn2_text'])}" placeholder="Apple Music or YouTube">
          <input type="text" name="btn2_url" value="{escape(data['btn2_url'])}" placeholder="https://music.apple.com/... or https://youtube.com/...">
        </div>
      </div>
    </div>

    <!-- Section 2: Booking & Press Email -->
    <div class="mm-card card">
      <div class="mm-card-title" style="font-size:16px; font-weight:700; margin-bottom:14px; color:#ffcc33;">📬 Booking &amp; Press Email</div>
      <div class="form-group">
        <label>Email Address</label>
        <input type="email" name="booking_email" value="{escape(data['booking_email'])}" placeholder="yourname@gmail.com">
        <p class="note">When visitors tap Booking &amp; Press, this email opens in their mail app. (Tip: Use a working Gmail or direct inbox until custom domain mail routing is configured).</p>
      </div>
    </div>

    <!-- Section 3: Orbit Platform Links & Toggles -->
    <div class="mm-card card">
      <div class="mm-card-title" style="font-size:16px; font-weight:700; margin-bottom:14px; color:#ffcc33;">🪐 Orbit Sites (The Icons Surrounding Top Stars)</div>
      
      <div class="platform-row">
        <input type="checkbox" name="spotify_show" {checked(data['spotify_show'])} id="chk_sp">
        <label for="chk_sp" class="platform-name">Spotify</label>
        <input type="text" class="platform-input" name="spotify_url" value="{escape(data['spotify_url'])}">
      </div>

      <div class="platform-row">
        <input type="checkbox" name="applemusic_show" {checked(data['applemusic_show'])} id="chk_ap">
        <label for="chk_ap" class="platform-name">Apple Music</label>
        <input type="text" class="platform-input" name="applemusic_url" value="{escape(data['applemusic_url'])}">
      </div>

      <div class="platform-row">
        <input type="checkbox" name="youtube_show" {checked(data['youtube_show'])} id="chk_yt">
        <label for="chk_yt" class="platform-name">YouTube</label>
        <input type="text" class="platform-input" name="youtube_url" value="{escape(data['youtube_url'])}">
      </div>

      <div class="platform-row">
        <input type="checkbox" name="instagram_show" {checked(data['instagram_show'])} id="chk_ig">
        <label for="chk_ig" class="platform-name">Instagram</label>
        <input type="text" class="platform-input" name="instagram_url" value="{escape(data['instagram_url'])}">
      </div>

      <div class="platform-row">
        <input type="checkbox" name="tiktok_show" {checked(data['tiktok_show'])} id="chk_tt">
        <label for="chk_tt" class="platform-name">TikTok</label>
        <input type="text" class="platform-input" name="tiktok_url" value="{escape(data['tiktok_url'])}">
      </div>
      <p class="note">Uncheck any site you want to hide from the orbit circle.</p>
    </div>
   </div>

   <!-- Sidebar: Publish Actions -->
   <aside class="side"><div class="mm-card">
    <div class="mm-card-title" style="font-weight:700; font-size:16px; margin-bottom:10px;">Save &amp; Publish</div>
    <p>Writes your changes to the site and immediately commits and pushes them to your live GitHub repository.</p>
    <button type="submit" class="mm-btn primary lg" style="width:100%; padding:14px; font-size:15px; font-weight:700; background:#ffcc33; color:#000; border:none; border-radius:10px; cursor:pointer;">Save &amp; Publish</button>
    <div id="status"></div>
   </div></aside>
  </form>

<script>
  function prev(input, imgId) {{
    if (input.files && input.files[0]) {{
      document.getElementById(imgId).src = URL.createObjectURL(input.files[0]);
      document.getElementById(imgId + '-name').textContent = input.files[0].name + ' · not published yet';
    }}
  }}
  const f = document.getElementById('f');
  const status = document.getElementById('status');
  f.addEventListener('submit', async (e) => {{
    e.preventDefault();
    if (!confirm('Publish these changes to your live page now? Your site will update in a minute or two.')) return;
    status.className = 'busy';
    status.textContent = 'Saving and publishing to GitHub…';
    try {{
      const res = await fetch('/save', {{ method: 'POST', body: new FormData(f) }});
      const data = await res.json();
      status.className = data.ok ? 'ok' : 'err';
      status.textContent = data.message;
    }} catch (err) {{
      status.className = 'err';
      status.textContent = 'Something went wrong: ' + err;
    }}
  }});
</script>
</div></body></html>"""


# ---------------------------------------------------------------- handler ----
def _serve_mm_ui(h):
    name = h.path.split("?")[0].rsplit("/", 1)[-1]
    if name in ("mm.css", "mm.js"):
        for up in Path(__file__).resolve().parents:
            f = up / "ui" / name
            if f.is_file():
                body = f.read_bytes()
                h.send_response(200)
                h.send_header("Content-Type", ("text/css" if name.endswith(".css") else "application/javascript") + "; charset=utf-8")
                h.send_header("Cache-Control", "no-cache")
                h.send_header("Content-Length", str(len(body)))
                h.end_headers()
                h.wfile.write(body)
                return
    h.send_response(404)
    h.send_header("Content-Length", "0")
    h.end_headers()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/ui/"):
            return _serve_mm_ui(self)
        if self.path == "/" or self.path.startswith("/?"):
            body = editor_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        if self.path != "/save":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "")
        boundary = ctype.split("boundary=")[-1].encode()
        fields, files = parse_multipart(body, boundary)

        try:
            save_site_data(fields, files)
            ok, message = git_publish()
        except Exception as e:
            ok, message = False, "Error while saving: " + str(e)

        out = json.dumps({"ok": ok, "message": message}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}/"
        print("\n  Shorty D Page Editor is running.")
        print(f"  Opening {url}")
        print("  (Leave this window open while editing. Close it when done.)\n")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  Editor closed.")


if __name__ == "__main__":
    main()
