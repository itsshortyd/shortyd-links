# Shorty D — Link Hub

A free, self-hosted "Linktree"-style page for Shorty D / Top Stars. Single HTML
file, no build tools, no paid services. Open `index.html` in any browser to see it.

## What's on the page

- Your big circular artist photo at the top (`assets/artist-photo.jpg`)
- Your "SHORTY D" name in graffiti-style lettering
- Your real Top Stars logo (transparent PNG, pulled straight from your
  overlay artwork) sitting in the center, with the platform icons (Spotify,
  Apple Music, YouTube, Instagram, TikTok) — each in its brand color —
  arranged in an orbit around it
- A bright background banner behind the top of the page that **changes when
  you hover/tap an icon** — it shows your "newest work" cover by default,
  and swaps to a platform-specific image (e.g. your newest tape for Spotify,
  newest video for YouTube, etc.) while you're hovering that icon. The page
  also samples that image's dominant color and tints the whole background
  with a soft hint of it (instead of staying flat white), so it always feels
  blended with whatever's on screen
- Clicking an icon makes it glow in that platform's brand color, then opens
  your profile link in a new tab

## ⭐ The easy way to update it (Edit My Page)

For the three things you change most — **profile photo**, **background image**,
and the **bottom "new release" message** — you don't need to touch any code:

1. Double-click **`Edit My Page.command`**.
2. A little editor opens in your browser. You'll see your current photo,
   background, and message.
3. Drop in a new photo and/or background, type a new message — change one thing
   or all three.
4. Hit **Save & Publish**. It saves the files *and* pushes them to your live
   page automatically. The live link updates in a minute or two.

That's it. Close the little black Terminal window when you're done.

(Under the hood that's `editor_server.py` — a tiny local helper. Photos are
auto-resized and rotated correctly, and the live page is told to grab the new
image right away so you don't see an old cached one.)

## How to run the page itself locally

Just double-click `index.html` — it opens in your default browser and works
completely offline (aside from loading the Google Fonts, which need internet).

## How to put your real links in

Open `index.html` in a text editor and find these placeholder URLs (search for
`REPLACE_WITH_YOUR_LINK`):

| Platform     | Line to edit                                                     |
|--------------|------------------------------------------------------------------|
| Spotify      | `href="https://open.spotify.com/artist/REPLACE_WITH_YOUR_LINK"`  |
| Apple Music  | `href="https://music.apple.com/artist/REPLACE_WITH_YOUR_LINK"`   |
| YouTube      | `href="https://youtube.com/@REPLACE_WITH_YOUR_LINK"`             |
| Instagram    | `href="https://instagram.com/REPLACE_WITH_YOUR_LINK"`            |
| TikTok       | `href="https://tiktok.com/@REPLACE_WITH_YOUR_LINK"`              |

Replace each `REPLACE_WITH_YOUR_LINK` with your actual handle/profile path.

## How to swap out images

All images live in the `assets/` folder:

- `artist-photo.jpg` — your circular profile photo at the top
- `no-days-off-cover.jpg` — the default "newest work" background image
- `topstars-logo.png` — the transparent Top Stars logo in the center
  (see "About the center logo" below)

**To change your profile photo or the default highlight image:** just replace
`artist-photo.jpg` or `no-days-off-cover.jpg` with a new file of the same name
(same folder, same filename — keeps everything wired up automatically). Any
image works; it'll get cropped to fit.

**To make the background dynamic per-platform** (e.g. show your newest tape
when someone hovers Spotify, newest video for YouTube, newest post for
Instagram, etc.): drop new image files into `assets/` (any name you like,
e.g. `newest-tape.jpg`, `newest-video-thumb.jpg`), then open `index.html`,
search for `data-bg="assets/no-days-off-cover.jpg"`, and change the path on
each platform's link to point at that platform's image. There are 5 of these
— one per icon — each right above its `<svg>` icon code, e.g.:

```html
<a class="orbit-icon" href="..." ... data-label="SPOTIFY · NEWEST TAPE" data-bg="assets/newest-tape.jpg" ...>
```

Just change `data-bg="..."` to the filename you dropped in. You can also edit
the text in `data-label="..."` — that's the caption that appears under the
orbit when that icon is active (e.g. "SPOTIFY · NEWEST TAPE").

Each link also has a `data-tint="#a02e18"` — a hex color that the page blends
softly into its background whenever that image is showing (this is what gives
the page its warm tint instead of staying flat white). If you swap in a new
image with very different coloring, grab its dominant color (any color-picker
tool/website works — drop the image in and hover to read the hex code) and
update `data-tint` to match so the tint keeps following the artwork.

If you'd rather keep it simple, leave all five `data-bg` paths pointing at the
same cover image — that's what's set up by default, so the background always
shows your latest project no matter which icon you're hovering.

## About the center logo

The center logo is your real Top Stars artwork
(`Desktop/Top Stars/Transparent Logo.png`), cropped tight to the star/text
mark and saved as `assets/topstars-logo.png` — a transparent PNG that sits
directly on the page with no background box, so nothing gets cut off or
boxed in. To swap it for a different version (white, yellow, etc.), replace
that file with another transparent PNG of the same name.

## About the platform icons

The 5 orbit icons use the official brand logos (via simple-icons), each set
in a circle badge filled with that platform's brand color — green for
Spotify, black for TikTok, red for YouTube, and brand gradients for Apple
Music and Instagram. To swap any icon's color, search `index.html` for
`--badge:` and edit the color/gradient value next to that platform's link.

## How to publish it for free (so the link works everywhere, 24/7)

Static hosts like **GitHub Pages**, **Netlify**, or **Vercel** will host this
page for free, permanently:

1. Create a free GitHub account and a new repository (e.g. `shortyd-links`)
2. Upload the whole `Website` folder's contents (`index.html` + `assets/`)
   into that repo
3. In the repo's Settings → Pages, set the source to the `main` branch
4. Your live link becomes something like:
   `https://yourusername.github.io/shortyd-links/`

Drop that link in your Instagram, TikTok, and Spotify bios — it runs forever,
for free, and updates instantly whenever you push new changes to the repo.

The only catch: you get the host's subdomain (not a `.com`). If you ever buy
`shortyd.com` or similar, you can point it at this same free-hosted page.
