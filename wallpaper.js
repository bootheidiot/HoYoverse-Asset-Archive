// wallpaper.js — shared across all pages
// Place your looping .mp4 files in the /wallpapers/ folder in your repo.
// Add the filenames to the WALLPAPERS array below and the script picks one randomly each load.

const WALLPAPERS = [
  "https://ia600102.us.archive.org/3/items/1920x-1080-to-be-fuel-for-the-night-event-animated-wallpaper/%5BUltrawide%5D%20To%20Be%20Fuel%20for%20the%20Night%20Event%20Animated%20Wallpaper.mp4",
  "https://ia601309.us.archive.org/10/items/1920x-1080-vivian-the-final-callback-event-animated-wallpaper/%5BUltrawide%5D%20Vivian%20The%20Final%20Callback%20Event%20Animated%20Wallpaper.mp4",
  "https://ia601501.us.archive.org/4/items/1920x-1080-sword-seeker-chronicles-event-animated-wallpaper/%5BUltrawide%5D%20Sword%20Seeker%20Chronicles%20Event%20Animated%20Wallpaper.mp4",
  "https://ia800102.us.archive.org/17/items/1920x-1080-special-visitor-event-animated-wallpaper/%5BUltrawide%5D%20Special%20Visitor%20Event%20Animated%20Wallpaper.mp4",
  "https://ia801607.us.archive.org/32/items/ye-shunguang-cleaving-to-the-truth-animated-wallpaper/%5BSource%5D%20Ye%20Shunguang%20Cleaving%20to%20the%20Truth%20Gacha%20Popup%20Animated%20Wallpaper.mp4",
  "https://ia601506.us.archive.org/13/items/spooky-tale-1-midnight-piano-mystery-yidharis-late-night-call-animated-wallpaper/Spooky%20Tale%201%20%27Midnight%20Piano%20Mystery%27%20-%20Yidhari%27s%20Late%20Night%20Call%20Animated%20Wallpaper.mp4",
  "https://archive.org/details/1920x-1080-when-dreams-remain-unfinished-event-animated-wallpaper",
  "https://ia800508.us.archive.org/3/items/1920x-1080-floral-voyage-into-the-unknown-tv-schedule-event-animated-wallpaper/%5BUltrawide%5D%20Floral%20Voyage%20Into%20the%20Unknown%20TV%20Schedule%20Event%20Animated%20Wallpaper.mp4",
  "https://ia601008.us.archive.org/9/items/1920x-1080-do-not-go-gentle-into-that-good-night-event-animated-wallpaper/%5BUltrawide%5D%20Do%20Not%20Go%20Gentle%20Into%20That%20Good%20Night%20Event%20Animated%20Wallpaper.mp4",
  "https://dn710003.ca.archive.org/0/items/the-impending-crash-of-waves-event-animated-wallpaper/%5BUltrawide%5D%20The%20Impending%20Crash%20of%20Waves%20Event%20Animated%20Wallpaper.mp4",
  
];

// Default accent color before video loads (Purple Amethyst)
const DEFAULT_ACCENT = '#9966CC';

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return {r, g, b};
}

function luminance(r, g, b) {
  return 0.299 * r + 0.587 * g + 0.114 * b;
}

function rgbToHex(r, g, b) {
  return '#' + [r,g,b].map(v => Math.round(v).toString(16).padStart(2,'0')).join('');
}

function adjustColor(r, g, b, targetLum) {
  const lum = luminance(r, g, b);
  if (lum === 0) return {r, g, b};
  const scale = targetLum / lum;
  return {
    r: Math.min(255, r * scale),
    g: Math.min(255, g * scale),
    b: Math.min(255, b * scale),
  };
}

function sampleVideoColor(video) {
  try {
    const canvas = document.createElement('canvas');
    canvas.width  = 64;
    canvas.height = 36;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, 64, 36);
    const data = ctx.getImageData(0, 0, 64, 36).data;

    let r = 0, g = 0, b = 0, count = 0;
    // Sample every 4th pixel for speed
    for (let i = 0; i < data.length; i += 16) {
      r += data[i];
      g += data[i+1];
      b += data[i+2];
      count++;
    }
    r /= count; g /= count; b /= count;

    // Boost saturation
    const avg = (r + g + b) / 3;
    const sat = 1.8;
    r = avg + (r - avg) * sat;
    g = avg + (g - avg) * sat;
    b = avg + (b - avg) * sat;
    r = Math.max(0, Math.min(255, r));
    g = Math.max(0, Math.min(255, g));
    b = Math.max(0, Math.min(255, b));

    return { r, g, b };
  } catch(e) {
    return null;
  }
}

function applyTheme(accentHex, immediate) {
  const { r, g, b } = hexToRgb(accentHex);
  const lum = luminance(r, g, b);

  // Derive dark bg from accent
  const dark  = adjustColor(r, g, b, 18);
  const darker = adjustColor(r, g, b, 10);
  const mid   = adjustColor(r, g, b, 40);
  const light = adjustColor(r, g, b, 80);
  const xlight = adjustColor(r, g, b, 220);

  // Text: white on dark bg
  const textColor   = '#ffffff';
  const mutedColor  = `rgba(255,255,255,0.6)`;
  const borderColor = `rgba(255,255,255,0.15)`;
  const surfaceColor = `rgba(255,255,255,0.07)`;

  const root = document.documentElement;
  const transition = immediate ? 'none' : 'background 1.2s ease, color 1s ease';
  root.style.setProperty('--transition-speed', transition);
  root.style.setProperty('--accent',       accentHex);
  root.style.setProperty('--accent-light', rgbToHex(mid.r, mid.g, mid.b));
  root.style.setProperty('--bg',           rgbToHex(darker.r, darker.g, darker.b));
  root.style.setProperty('--surface',      surfaceColor);
  root.style.setProperty('--text',         textColor);
  root.style.setProperty('--muted',        mutedColor);
  root.style.setProperty('--border',       borderColor);
  root.style.setProperty('--gold',         accentHex);
  root.style.setProperty('--nav-bg',       `rgba(${dark.r},${dark.g},${dark.b},0.85)`);
  root.style.setProperty('--footer-bg',    `rgba(${darker.r},${darker.g},${darker.b},0.9)`);
}

function initWallpaper() {
  // Apply default theme immediately
  applyTheme(DEFAULT_ACCENT, true);

  if (WALLPAPERS.length === 0) return;

  // Pick a random wallpaper
  const src = WALLPAPERS[Math.floor(Math.random() * WALLPAPERS.length)];

  // Create video element
  const video = document.createElement('video');
  video.src      = src;
  video.autoplay = true;
  video.loop     = true;
  video.muted    = true;
  video.playsInline = true;
  video.style.cssText = `
    position: fixed;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    z-index: -1;
    opacity: 0;
    transition: opacity 1.5s ease;
    pointer-events: none;
  `;

  document.body.appendChild(video);

  // Add dark overlay so text stays readable
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.45);
    z-index: -1;
    pointer-events: none;
  `;
  document.body.appendChild(overlay);

  video.addEventListener('canplay', () => {
    video.style.opacity = '1';
    video.play().catch(() => {});
  });

  // Sample color from video periodically and update theme
  let colorInterval = null;
  video.addEventListener('playing', () => {
    const sample = () => {
      const color = sampleVideoColor(video);
      if (color) {
        const hex = rgbToHex(color.r, color.g, color.b);
        applyTheme(hex, false);
      }
    };
    sample();
    colorInterval = setInterval(sample, 3000);
  });

  video.addEventListener('error', () => {
    console.warn('Wallpaper video failed to load:', src);
  });
}

document.addEventListener('DOMContentLoaded', initWallpaper);
