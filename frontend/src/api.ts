import type { Mode } from "./presets";

// 本番はCloudFront経由の同一オリジン。開発時はVITE_API_BASEでCF/API GWのURLを指定
const API_BASE: string = import.meta.env.VITE_API_BASE ?? "";

export interface CreateJobRequest {
  mode: Mode;
  filename: string;
  targetSizeMb?: number;
  resolutionWidth?: number | null;
  audioBitrateKbps?: number;
  gifWidth?: number | null;
  gifFps?: number | null;
}

export interface CreateJobResponse {
  jobId: string;
  upload: { url: string; fields: Record<string, string> };
  maxUploadBytes: number;
}

export interface JobStatus {
  jobId: string;
  status: "pending" | "processing" | "completed" | "failed";
  mode: Mode;
  filename: string;
  progress: number;
  error?: string;
  attempt?: number;
  maxAttempts?: number;
  outputSizeBytes?: number;
  downloadUrl?: string;
}

export async function createJob(req: CreateJobRequest): Promise<CreateJobResponse> {
  const res = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `ジョブ作成に失敗しました (HTTP ${res.status})`);
  }
  return res.json();
}

export function uploadFile(
  upload: CreateJobResponse["upload"],
  file: File,
  onProgress: (ratio: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    Object.entries(upload.fields).forEach(([k, v]) => form.append(k, v));
    form.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new Error(`アップロードに失敗しました (HTTP ${xhr.status})`));
    };
    xhr.onerror = () => reject(new Error("アップロード中にネットワークエラーが発生しました"));
    xhr.open("POST", upload.url);
    xhr.send(form);
  });
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `ステータス取得に失敗しました (HTTP ${res.status})`);
  }
  return res.json();
}
