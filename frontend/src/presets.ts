// config.py のプリセットを移植
export type Mode = "video" | "gif_resize" | "gif_compress";

export const MODE_LABELS: Record<Mode, string> = {
  video: "動画圧縮",
  gif_resize: "GIFリサイズ",
  gif_compress: "GIF圧縮",
};

export const RESOLUTION_PRESETS: { label: string; width: number | null }[] = [
  { label: "オリジナル", width: null },
  { label: "1080p (1920x1080)", width: 1920 },
  { label: "720p (1280x720)", width: 1280 },
  { label: "480p (854x480)", width: 854 },
  { label: "360p (640x360)", width: 640 },
];

export const AUDIO_BITRATE_PRESETS: { label: string; kbps: number }[] = [
  { label: "64 kbps (低品質)", kbps: 64 },
  { label: "96 kbps", kbps: 96 },
  { label: "128 kbps (標準)", kbps: 128 },
  { label: "192 kbps (高品質)", kbps: 192 },
  { label: "256 kbps (最高品質)", kbps: 256 },
];

export const GIF_WIDTH_PRESETS: { label: string; width: number | null }[] = [
  { label: "オリジナル", width: null },
  { label: "800px", width: 800 },
  { label: "640px", width: 640 },
  { label: "480px", width: 480 },
  { label: "320px", width: 320 },
];

export const GIF_FPS_PRESETS: { label: string; fps: number | null }[] = [
  { label: "オリジナル", fps: null },
  { label: "15 fps", fps: 15 },
  { label: "12 fps", fps: 12 },
  { label: "10 fps", fps: 10 },
  { label: "8 fps", fps: 8 },
];

export const VIDEO_ACCEPT = ".mp4,.mov,.m4v,.avi,.mkv,.webm";
export const GIF_ACCEPT = ".gif";
