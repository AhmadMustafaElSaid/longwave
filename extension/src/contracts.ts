export type JobState =
  | "queued"
  | "resolving"
  | "downloading"
  | "paused"
  | "processing"
  | "verifying"
  | "completed"
  | "failed"
  | "cancelled";
export interface Job {
  id: string;
  url: string;
  format: "original" | "mp3";
  state: JobState;
  desired: "running" | "paused" | "cancelled";
  title: string;
  artist: string;
  duration: number | null;
  bytes: number;
  total: number | null;
  speed: number | null;
  eta: number | null;
  progress: number | null;
  created: number;
  updated: number;
  error: { code: string; message: string } | null;
  output: string | null;
  note: string | null;
  codec: string | null;
  source_bitrate: number | null;
}
export interface Snapshot {
  version: string;
  protocol: number;
  tools: { extractor: boolean; ffmpeg: boolean; ffprobe: boolean };
  outputDir: string;
  jobs: Job[];
}
export type Command =
  | { version: 1; command: "snapshot" }
  | { version: 1; command: "create"; requestId: string; url: string; format: "original" | "mp3" }
  | { version: 1; command: "pause" | "resume" | "cancel" | "reveal"; id: string };
export type Reply<T> =
  { ok: true; data: T } | { ok: false; error: { code: string; message: string } };

export function isSnapshot(value: unknown): value is Snapshot {
  if (!value || typeof value !== "object") return false;
  const data = value as Partial<Snapshot>;
  return (
    data.protocol === 1 &&
    typeof data.version === "string" &&
    typeof data.outputDir === "string" &&
    typeof data.tools?.extractor === "boolean" &&
    typeof data.tools.ffmpeg === "boolean" &&
    typeof data.tools.ffprobe === "boolean" &&
    Array.isArray(data.jobs) &&
    data.jobs.every(
      (job: Partial<Job>) =>
        typeof job.id === "string" &&
        typeof job.title === "string" &&
        typeof job.artist === "string" &&
        typeof job.state === "string" &&
        typeof job.bytes === "number",
    )
  );
}
