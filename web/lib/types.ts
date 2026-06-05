export type TaskStatus = "idle" | "pending" | "running" | "done" | "error";

export interface TaskEvent {
  status: TaskStatus;
  message: string;
  progress: number;
  result?: TranscribeResult;
  error?: string;
}

export interface TranscribeResult {
  title: string;
  text: string;
  markdown: string;
  srt: string;
  segments: number;
  elapsed: number;
  video_id?: string;
  slides?: number;
  slides_error?: string;
  ocr_frames?: number;
  stt_source?: string;
}

export interface HarnessFile {
  path: string;
  content: string;
  info: string;
}

export interface HarnessOverview {
  constitution: string;
  specs: string;
  tests: string;
  workflows: string;
}

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9102";

export const MODELS = [
  { value: "mlx-community/whisper-large-v3-turbo", label: "large-v3-turbo (권장)" },
  { value: "mlx-community/whisper-large-v3", label: "large-v3 (최고 품질)" },
  { value: "mlx-community/whisper-small", label: "small (가벼움)" },
];

export const LANGUAGES = [
  { value: "ko", label: "한국어" },
  { value: "en", label: "영어" },
  { value: "ja", label: "일본어" },
  { value: "zh", label: "중국어" },
];

export interface Playlist {
  id: string;
  title: string;
  description: string;
  channel: string;
  source_url: string;
  thumbnail: string;
  item_count: number;
  youtube_playlist_id: string;
}

export interface PlaylistVideo {
  id: string;
  title: string;
  thumbnail: string;
  position: number;
}
