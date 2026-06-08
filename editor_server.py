#!/usr/bin/env python3
"""
Shorty D — Page Editor
----------------------
A tiny local app for quickly changing the three things you touch most:

  1. Profile photo (the big circle)
  2. Background image (the banner behind everything)
  3. Bottom message (the "NEWEST DROP ..." line)

Double-click "Edit My Page.command" (or run `python3 editor_server.py`),
make your changes in the browser, hit "Save & Publish" — it writes the
files, commits, and pushes them live to your GitHub Pages link.

No HTML editing, ever.
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

try:
    from PIL import Image, ImageOps
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")
ASSETS = os.path.join(HERE, "assets")
PROFILE_FILE = "assets/artist-photo.jpg"
BG_FILE = "assets/no-days-off-cover.jpg"
PORT = 7440
LIVE_URL = "https://itsshortyd.github.io/shortyd-links/"


# ---------------------------------------------------------------- helpers ----
def read_index():
    with open(INDEX, "r", encoding="utf-8") as f:
        return f.read()


def write_index(text):
    with open(INDEX, "w", encoding="utf-8") as f:
        f.write(text)


def current_message():
    """Pull the current bottom message out of the page."""
    m = re.search(r'id="platformLabel">(.*?)</p>', read_index(), re.S)
    return m.group(1).strip() if m else ""


def set_message(new_msg):
    """Replace the bottom message (single source of truth in the HTML)."""
    safe = escape(new_msg.strip(), quote=False)
    html = read_index()
    html = re.sub(
        r'(id="platformLabel">).*?(</p>)',
        lambda m: m.group(1) + safe + m.group(2),
        html,
        count=1,
        flags=re.S,
    )
    write_index(html)


def bump_cache_version(asset_path):
    """
    Add/refresh a ?v=<timestamp> on every reference to this asset so the
    live site shows the new image immediately instead of a cached one.
    """
    html = read_index()
    stamp = str(int(time.time()))
    base = re.escape(asset_path)
    # asset_path optionally followed by ?v=NNN, inside quotes
    html = re.sub(base + r'(?:\?v=\d+)?', asset_path + "?v=" + stamp, html)
    write_index(html)


def save_image(raw_bytes, dest_filename):
    """Normalize an uploaded image to a clean JPEG at the fixed filename."""
    dest = os.path.join(HERE, dest_filename)
    if HAVE_PIL:
        try:
            img = Image.open(io.BytesIO(raw_bytes))
            img = ImageOps.exif_transpose(img)        # respect phone rotation
            img = img.convert("RGB")
            # keep files reasonable for fast loading
            img.thumbnail((1600, 1600))
            img.save(dest, "JPEG", quality=88, optimize=True)
            return
        except Exception:
            pass  # fall through to raw write
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
        subprocess.run(["git", "-C", HERE, "add", "-A"], check=True,
                       capture_output=True)
        status = subprocess.run(["git", "-C", HERE, "status", "--porcelain"],
                                capture_output=True, text=True).stdout.strip()
        if not status:
            return True, "No changes to publish — everything was already up to date."
        subprocess.run(
            ["git", "-C", HERE, "commit", "-m", "Update page via editor"],
            check=True, capture_output=True)
        push = subprocess.run(["git", "-C", HERE, "push"],
                              capture_output=True, text=True)
        if push.returncode != 0:
            return False, "Saved locally, but publish failed:\n" + push.stderr.strip()
        return True, "Published! Your live page will update in a minute or two."
    except subprocess.CalledProcessError as e:
        return False, "Git error:\n" + (e.stderr.decode() if e.stderr else str(e))


# ------------------------------------------------------------------- page ----
def editor_page():
    msg = escape(current_message())
    cb = int(time.time())  # cache-bust the previews in the editor itself
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Edit Shorty D's Page</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 0;
         background: #14110e; color: #f6f0e4; display: flex;
         justify-content: center; padding: 32px 16px 80px; }}
  .wrap {{ width: 100%; max-width: 560px; }}
  h1 {{ font-size: 26px; margin: 0 0 4px; }}
  .sub {{ color: #b6a890; margin: 0 0 28px; font-size: 14px; }}
  .card {{ background: #211b15; border: 1px solid #3a2f24; border-radius: 16px;
          padding: 20px; margin-bottom: 18px; }}
  .card h2 {{ font-size: 15px; letter-spacing: .5px; text-transform: uppercase;
             color: #ffcc33; margin: 0 0 14px; }}
  .row {{ display: flex; gap: 16px; align-items: center; }}
  .thumb {{ background: #14110e; border: 1px solid #3a2f24; border-radius: 12px;
           overflow: hidden; flex: 0 0 auto; }}
  .thumb.circle {{ width: 96px; height: 96px; border-radius: 50%; }}
  .thumb.banner {{ width: 160px; height: 96px; }}
  .thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .pick {{ flex: 1; }}
  input[type=file] {{ width: 100%; color: #b6a890; font-size: 13px; }}
  input[type=text] {{ width: 100%; padding: 14px; font-size: 17px;
                     background: #14110e; color: #fff; border: 1px solid #3a2f24;
                     border-radius: 10px; }}
  .note {{ color: #8a7c69; font-size: 12px; margin: 8px 0 0; }}
  button {{ width: 100%; padding: 16px; font-size: 17px; font-weight: 600;
           background: #ffcc33; color: #211b15; border: 0; border-radius: 12px;
           cursor: pointer; margin-top: 6px; }}
  button:active {{ transform: translateY(1px); }}
  #status {{ margin-top: 16px; padding: 14px; border-radius: 10px; font-size: 14px;
            white-space: pre-wrap; display: none; }}
  #status.ok {{ background: #1d3320; color: #b8f0c0; display: block; }}
  #status.err {{ background: #3a1d1d; color: #f0b8b8; display: block; }}
  #status.busy {{ background: #2a2419; color: #ffcc33; display: block; }}
  a {{ color: #ffcc33; }}
</style></head>
<body><div class="wrap">
  <h1>Edit Shorty D's Page</h1>
  <p class="sub">Change a thing, hit Save &amp; Publish. That's it.
     <a href="{LIVE_URL}" target="_blank">View live page ↗</a></p>

  <form id="f">
    <div class="card">
      <h2>Profile photo</h2>
      <div class="row">
        <div class="thumb circle"><img id="pp" src="{PROFILE_FILE}?v={cb}"></div>
        <div class="pick">
          <input type="file" name="profile" accept="image/*"
                 onchange="prev(this,'pp')">
          <p class="note">The big circle at the top.</p>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Background image</h2>
      <div class="row">
        <div class="thumb banner"><img id="bg" src="{BG_FILE}?v={cb}"></div>
        <div class="pick">
          <input type="file" name="background" accept="image/*"
                 onchange="prev(this,'bg')">
          <p class="note">The banner behind everything.</p>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Bottom message</h2>
      <input type="text" name="message" value="{msg}"
             placeholder='e.g. NEW SINGLE OUT NOW'>
      <p class="note">The line under the icons (your "new release" text).</p>
    </div>

    <button type="submit">Save &amp; Publish</button>
    <div id="status"></div>
  </form>

<script>
  function prev(input, imgId) {{
    if (input.files && input.files[0])
      document.getElementById(imgId).src = URL.createObjectURL(input.files[0]);
  }}
  const f = document.getElementById('f');
  const status = document.getElementById('status');
  f.addEventListener('submit', async (e) => {{
    e.preventDefault();
    status.className = 'busy';
    status.textContent = 'Saving and publishing…';
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
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def log_message(self, *a):
        pass  # quiet

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            body = editor_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        # serve assets/index for previews, with no caching
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
            if "profile" in files:
                save_image(files["profile"], PROFILE_FILE)
                bump_cache_version(PROFILE_FILE)
            if "background" in files:
                save_image(files["background"], BG_FILE)
                bump_cache_version(BG_FILE)
            if "message" in fields:
                set_message(fields["message"])
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
