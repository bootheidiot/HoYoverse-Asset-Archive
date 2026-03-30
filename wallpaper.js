// wallpaper.js — shared across all pages
// Add your video URLs to the WALLPAPERS array below.
// Supports direct URLs (Archive.org, etc). A random one is picked each page load.

const WALLPAPERS = [
  "https://ia600102.us.archive.org/3/items/1920x-1080-to-be-fuel-for-the-night-event-animated-wallpaper/%5BUltrawide%5D%20To%20Be%20Fuel%20for%20the%20Night%20Event%20Animated%20Wallpaper.mp4",
  "https://ia601309.us.archive.org/10/items/1920x-1080-vivian-the-final-callback-event-animated-wallpaper/%5BUltrawide%5D%20Vivian%20The%20Final%20Callback%20Event%20Animated%20Wallpaper.mp4",
  "https://ia601501.us.archive.org/4/items/1920x-1080-sword-seeker-chronicles-event-animated-wallpaper/%5BUltrawide%5D%20Sword%20Seeker%20Chronicles%20Event%20Animated%20Wallpaper.mp4",
  "https://ia800102.us.archive.org/17/items/1920x-1080-special-visitor-event-animated-wallpaper/%5BUltrawide%5D%20Special%20Visitor%20Event%20Animated%20Wallpaper.mp4",
  "https://ia801607.us.archive.org/32/items/ye-shunguang-cleaving-to-the-truth-animated-wallpaper/%5BSource%5D%20Ye%20Shunguang%20Cleaving%20to%20the%20Truth%20Gacha%20Popup%20Animated%20Wallpaper.mp4",
  "https://ia601506.us.archive.org/13/items/spooky-tale-1-midnight-piano-mystery-yidharis-late-night-call-animated-wallpaper/Spooky%20Tale%201%20%27Midnight%20Piano%20Mystery%27%20-%20Yidhari%27s%20Late%20Night%20Call%20Animated%20Wallpaper.mp4",
  "https://ia600809.us.archive.org/13/items/1920x-1080-when-dreams-remain-unfinished-event-animated-wallpaper/%5BUltrawide%5D%20When%20Dreams%20Remain%20Unfinished%20Event%20Animated%20Wallpaper.mp4",
  "https://ia800508.us.archive.org/3/items/1920x-1080-floral-voyage-into-the-unknown-tv-schedule-event-animated-wallpaper/%5BUltrawide%5D%20Floral%20Voyage%20Into%20the%20Unknown%20TV%20Schedule%20Event%20Animated%20Wallpaper.mp4",
  "https://ia601008.us.archive.org/9/items/1920x-1080-do-not-go-gentle-into-that-good-night-event-animated-wallpaper/%5BUltrawide%5D%20Do%20Not%20Go%20Gentle%20Into%20That%20Good%20Night%20Event%20Animated%20Wallpaper.mp4",
  "https://dn710003.ca.archive.org/0/items/the-impending-crash-of-waves-event-animated-wallpaper/%5BUltrawide%5D%20The%20Impending%20Crash%20of%20Waves%20Event%20Animated%20Wallpaper.mp4",
  "https://ia800405.us.archive.org/21/items/1920x-1080-new-eridan-sunset-a-event-animated-wallpaper/%5BUltrawide%5D%20New%3B%20Eridan%20Sunset%20%28A%29%20Event%20Animated%20Wallpaper.mp4",
  "https://ia601701.us.archive.org/9/items/1920x-1080-neo-golden-mecha-event-animated-wallpaper/%5BUltrawide%5D%20Neo%20Golden%20Mecha%20Event%20Animated%20Wallpaper.mp4",
  "https://ia601703.us.archive.org/7/items/1920x-1080-100-miss-bunny-event-animated-wallpaper/%5BUltrawide%5D%20100%25%20Miss%20Bunny%20Event%20Animated%20Wallpaper.mp4",
  "https://ia801508.us.archive.org/27/items/1-sleepless-whispers-zenless-zone-zero/%5B2560x1440%5D%20Lucia%20Brushing%20-%20Zenless%20Zone%20Zero%20%27Sleepless%20Whispers%27.mp4"
];

const DEFAULT_ACCENT = '#9966CC';

// ── COLOR UTILITIES ──────────────────────────────────────────────────────────

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1,3), 16);
  const g = parseInt(hex.slice(3,5), 16);
  const b = parseInt(hex.slice(5,7), 16);
  return { r, g, b };
}

function luminance(r, g, b) {
  return 0.299 * r + 0.587 * g + 0.114 * b;
}

function rgbToHex(r, g, b) {
  return '#' + [r, g, b].map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');
}

function adjustLuminance(r, g, b, target) {
  const lum = luminance(r, g, b);
  if (lum === 0) return { r, g, b };
  const scale = target / lum;
  return {
    r: Math.min(255, r * scale),
    g: Math.min(255, g * scale),
    b: Math.min(255, b * scale),
  };
}

function sampleVideoColor(video) {
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 36;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, 64, 36);
    const data = ctx.getImageData(0, 0, 64, 36).data;

    let r = 0, g = 0, b = 0, count = 0;
    for (let i = 0; i < data.length; i += 16) {
      r += data[i]; g += data[i+1]; b += data[i+2]; count++;
    }
    r /= count; g /= count; b /= count;

    // Boost saturation so muted video colors still produce vivid accents
    const avg = (r + g + b) / 3;
    const sat = 2.2;
    r = avg + (r - avg) * sat;
    g = avg + (g - avg) * sat;
    b = avg + (b - avg) * sat;
    r = Math.max(0, Math.min(255, r));
    g = Math.max(0, Math.min(255, g));
    b = Math.max(0, Math.min(255, b));

    // Make sure it's vivid enough to use
    if (luminance(r, g, b) < 5) return null;
    return { r, g, b };
  } catch (e) {
    // Canvas tainted by CORS — can't sample, keep current theme
    return null;
  }
}

// ── THEME APPLICATION ────────────────────────────────────────────────────────

function applyTheme(r, g, b) {
  const darker  = adjustLuminance(r, g, b, 12);
  const dark    = adjustLuminance(r, g, b, 22);
  const accent  = rgbToHex(r, g, b);
  const bgHex   = rgbToHex(darker.r, darker.g, darker.b);
  const navHex  = `rgba(${Math.round(darker.r)},${Math.round(darker.g)},${Math.round(darker.b)},0.88)`;

  const root = document.documentElement;
  root.style.setProperty('--accent',      accent);
  root.style.setProperty('--gold',        accent);
  root.style.setProperty('--bg',          bgHex);
  root.style.setProperty('--nav-bg',      navHex);
  root.style.setProperty('--footer-bg',   navHex);
  root.style.setProperty('--accent-light', rgbToHex(dark.r, dark.g, dark.b));
}

// ── WALLPAPER INIT ───────────────────────────────────────────────────────────

function initWallpaper() {
  // Apply default purple theme immediately
  const def = hexToRgb(DEFAULT_ACCENT);
  applyTheme(def.r, def.g, def.b);

  if (WALLPAPERS.length === 0) return;

  // Inject required base styles onto body so page content always sits on top
  document.body.style.position = 'relative';

  // ── Video element (fixed, behind everything) ──
  const video = document.createElement('video');
  video.muted      = true;
  video.autoplay   = true;
  video.loop       = true;
  video.playsInline = true;
  // NOTE: crossOrigin is intentionally NOT set — Archive.org blocks CORS requests.
  // Videos will play fine; canvas color sampling is skipped and default theme is used.
  video.style.cssText = [
    'position: fixed',
    'top: 0',
    'left: 0',
    'width: 100vw',
    'height: 100vh',
    'object-fit: cover',
    'z-index: -2',         // behind everything
    'opacity: 0',
    'transition: opacity 1.8s ease',
    'pointer-events: none',
  ].join(';');

  // ── Dark overlay (fixed, behind content but above video) ──
  const overlay = document.createElement('div');
  overlay.style.cssText = [
    'position: fixed',
    'top: 0',
    'left: 0',
    'width: 100vw',
    'height: 100vh',
    'background: rgba(0,0,0,0.52)',
    'z-index: -1',         // above video, below page content
    'pointer-events: none',
  ].join(';');

  // Insert both before any other children so DOM order doesn't fight z-index
  document.body.insertBefore(overlay, document.body.firstChild);
  document.body.insertBefore(video, document.body.firstChild);

  // Pick a random wallpaper
  const src = WALLPAPERS[Math.floor(Math.random() * WALLPAPERS.length)];
  video.src = src;

  video.addEventListener('canplay', () => {
    video.play().catch(() => {});
    video.style.opacity = '1';
  });

  // Try to sample color. If CORS blocks it we just keep the default theme.
  let colorSampled = false;
  let colorInterval = null;

  video.addEventListener('playing', () => {
    if (colorInterval) return;
    const trySample = () => {
      const color = sampleVideoColor(video);
      if (color) {
        applyTheme(color.r, color.g, color.b);
        colorSampled = true;
      }
      // If null (CORS blocked), keep current theme — don't spam errors
    };
    trySample();
    colorInterval = setInterval(trySample, 4000);
  });

  video.addEventListener('error', () => {
    console.warn('[wallpaper] Could not load video:', src);
    // Try next video in list
    const remaining = WALLPAPERS.filter(w => w !== src);
    if (remaining.length > 0) {
      video.src = remaining[Math.floor(Math.random() * remaining.length)];
    }
  });
}

document.addEventListener('DOMContentLoaded', initWallpaper);
