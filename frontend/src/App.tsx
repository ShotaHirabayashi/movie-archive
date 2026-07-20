import { useCallback, useEffect, useRef, useState } from "react";
import { createJob, getJob, uploadFile, type JobStatus } from "./api";
import { Button } from "./components/button";
import { Field, FieldGroup, Fieldset, Label } from "./components/fieldset";
import { Heading } from "./components/heading";
import { Input } from "./components/input";
import { Select } from "./components/select";
import { Text } from "./components/text";
import {
  AUDIO_BITRATE_PRESETS,
  GIF_ACCEPT,
  GIF_FPS_PRESETS,
  GIF_WIDTH_PRESETS,
  MODE_LABELS,
  RESOLUTION_PRESETS,
  VIDEO_ACCEPT,
  type Mode,
} from "./presets";

type Phase = "idle" | "creating" | "uploading" | "waiting" | "processing" | "completed" | "failed";

const POLL_INTERVAL_MS = 2000;
const GIVE_UP_MS = 20 * 60 * 1000; // Lambda上限15分+余裕

function formatMb(bytes: number): string {
  return (bytes / (1024 * 1024)).toFixed(2);
}

function ProgressBar({ ratio }: { ratio: number }) {
  return (
    <div className="h-2.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
      <div
        className="h-full rounded-full bg-indigo-500 transition-[width] duration-300 ease-out"
        style={{ width: `${Math.round(ratio * 100)}%` }}
      />
    </div>
  );
}

export default function App() {
  const [mode, setMode] = useState<Mode>("video");
  const [file, setFile] = useState<File | null>(null);
  const [targetSizeMb, setTargetSizeMb] = useState(10);
  const [resolutionWidth, setResolutionWidth] = useState<number | null>(null);
  const [audioBitrateKbps, setAudioBitrateKbps] = useState(128);
  const [gifWidth, setGifWidth] = useState<number | null>(null);
  const [gifFps, setGifFps] = useState<number | null>(null);

  const [phase, setPhase] = useState<Phase>("idle");
  const [uploadRatio, setUploadRatio] = useState(0);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const pollTimer = useRef<number | null>(null);
  const startedAt = useRef(0);

  const stopPolling = useCallback(() => {
    if (pollTimer.current !== null) {
      window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const reset = () => {
    stopPolling();
    setPhase("idle");
    setFile(null);
    setJob(null);
    setErrorMsg("");
    setUploadRatio(0);
  };

  const busy = phase === "creating" || phase === "uploading" || phase === "waiting" || phase === "processing";

  const changeMode = (m: Mode) => {
    if (busy) return;
    setMode(m);
    reset();
  };

  const startPolling = (jobId: string) => {
    startedAt.current = Date.now();
    setPhase("waiting");
    pollTimer.current = window.setInterval(async () => {
      try {
        const status = await getJob(jobId);
        setJob(status);
        if (status.status === "processing") setPhase("processing");
        if (status.status === "completed") {
          stopPolling();
          setPhase("completed");
        } else if (status.status === "failed") {
          stopPolling();
          setPhase("failed");
          setErrorMsg(status.error ?? "圧縮に失敗しました");
        } else if (Date.now() - startedAt.current > GIVE_UP_MS) {
          stopPolling();
          setPhase("failed");
          setErrorMsg("処理がタイムアウトしました。ファイルが大きすぎる可能性があります（実行上限は15分です）");
        }
      } catch {
        // 一時的なネットワークエラーはポーリング継続
      }
    }, POLL_INTERVAL_MS);
  };

  const start = async () => {
    if (!file) return;
    setErrorMsg("");
    try {
      setPhase("creating");
      const res = await createJob({
        mode,
        filename: file.name,
        ...(mode !== "gif_resize" ? { targetSizeMb } : {}),
        ...(mode === "video" ? { resolutionWidth, audioBitrateKbps } : {}),
        ...(mode === "gif_resize" ? { gifWidth, gifFps } : {}),
      });
      if (file.size > res.maxUploadBytes) {
        throw new Error(`ファイルが大きすぎます（上限 ${formatMb(res.maxUploadBytes)} MB）`);
      }
      setPhase("uploading");
      await uploadFile(res.upload, file, setUploadRatio);
      startPolling(res.jobId);
    } catch (e) {
      setPhase("failed");
      setErrorMsg(e instanceof Error ? e.message : String(e));
    }
  };

  const accept = mode === "video" ? VIDEO_ACCEPT : GIF_ACCEPT;
  const progress = job?.progress ?? 0;

  return (
    <main className="mx-auto max-w-xl px-4 py-10 sm:py-16">
      <div className="text-center">
        <Heading level={1}>🎬 Movie Cut</Heading>
        <Text className="mt-2">動画・GIFを目標サイズに圧縮</Text>
      </div>

      <nav className="mt-8 grid grid-cols-3 gap-2">
        {(Object.keys(MODE_LABELS) as Mode[]).map((m) =>
          m === mode ? (
            <Button key={m} color="indigo" disabled={busy}>
              {MODE_LABELS[m]}
            </Button>
          ) : (
            <Button key={m} outline onClick={() => changeMode(m)} disabled={busy}>
              {MODE_LABELS[m]}
            </Button>
          ),
        )}
      </nav>

      <section className="mt-6 rounded-2xl border border-zinc-950/10 bg-white p-6 shadow-xs dark:border-white/10 dark:bg-zinc-800/50">
        <label className="flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-zinc-950/15 px-4 py-10 text-center transition-colors hover:border-indigo-400 dark:border-white/15 dark:hover:border-indigo-400">
          <input
            type="file"
            accept={accept}
            className="sr-only"
            disabled={busy}
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setJob(null);
              setErrorMsg("");
              if (phase !== "idle") setPhase("idle");
            }}
          />
          {file ? (
            <>
              <Text className="font-medium break-all">{file.name}</Text>
              <Text className="text-sm">{formatMb(file.size)} MB</Text>
            </>
          ) : (
            <Text>
              {mode === "video" ? "動画ファイルを選択（最大1GB）" : "GIFファイルを選択（最大1GB）"}
            </Text>
          )}
        </label>

        <Fieldset className="mt-6" disabled={busy}>
          <FieldGroup>
            {mode !== "gif_resize" && (
              <Field>
                <Label>目標ファイルサイズ (MB)</Label>
                <Input
                  type="number"
                  min={0.1}
                  max={2048}
                  step={mode === "gif_compress" ? 0.5 : 1}
                  value={targetSizeMb}
                  onChange={(e) => setTargetSizeMb(Number(e.target.value))}
                />
              </Field>
            )}

            {mode === "video" && (
              <>
                <Field>
                  <Label>解像度</Label>
                  <Select
                    value={String(resolutionWidth)}
                    onChange={(e) => setResolutionWidth(e.target.value === "null" ? null : Number(e.target.value))}
                  >
                    {RESOLUTION_PRESETS.map((p) => (
                      <option key={p.label} value={String(p.width)}>{p.label}</option>
                    ))}
                  </Select>
                </Field>
                <Field>
                  <Label>音声ビットレート</Label>
                  <Select
                    value={audioBitrateKbps}
                    onChange={(e) => setAudioBitrateKbps(Number(e.target.value))}
                  >
                    {AUDIO_BITRATE_PRESETS.map((p) => (
                      <option key={p.kbps} value={p.kbps}>{p.label}</option>
                    ))}
                  </Select>
                </Field>
              </>
            )}

            {mode === "gif_resize" && (
              <>
                <Field>
                  <Label>幅</Label>
                  <Select
                    value={String(gifWidth)}
                    onChange={(e) => setGifWidth(e.target.value === "null" ? null : Number(e.target.value))}
                  >
                    {GIF_WIDTH_PRESETS.map((p) => (
                      <option key={p.label} value={String(p.width)}>{p.label}</option>
                    ))}
                  </Select>
                </Field>
                <Field>
                  <Label>フレームレート</Label>
                  <Select
                    value={String(gifFps)}
                    onChange={(e) => setGifFps(e.target.value === "null" ? null : Number(e.target.value))}
                  >
                    {GIF_FPS_PRESETS.map((p) => (
                      <option key={p.label} value={String(p.fps)}>{p.label}</option>
                    ))}
                  </Select>
                </Field>
              </>
            )}
          </FieldGroup>
        </Fieldset>

        <Button color="indigo" className="mt-6 w-full" onClick={start} disabled={!file || busy}>
          {busy ? "処理中..." : "開始"}
        </Button>

        {phase === "uploading" && (
          <div className="mt-5 flex flex-col gap-2">
            <Text className="text-sm">アップロード中... {Math.round(uploadRatio * 100)}%</Text>
            <ProgressBar ratio={uploadRatio} />
          </div>
        )}

        {(phase === "waiting" || phase === "processing") && (
          <div className="mt-5 flex flex-col gap-2">
            <Text className="text-sm">
              {phase === "waiting"
                ? "処理開始を待っています..."
                : job?.attempt
                  ? `圧縮中（試行 ${job.attempt}/${job.maxAttempts}）... ${Math.round(progress * 100)}%`
                  : `圧縮中... ${Math.round(progress * 100)}%`}
            </Text>
            <ProgressBar ratio={progress} />
          </div>
        )}

        {phase === "completed" && job && (
          <div className="mt-5 flex flex-col gap-3 rounded-xl bg-emerald-500/10 p-4">
            <Text>
              ✅ 完了！ 出力サイズ: <strong>{formatMb(job.outputSizeBytes ?? 0)} MB</strong>
            </Text>
            <Button color="emerald" href={job.downloadUrl}>
              ダウンロード
            </Button>
            <Button plain onClick={reset}>別のファイルを圧縮する</Button>
          </div>
        )}

        {phase === "failed" && (
          <div className="mt-5 flex flex-col gap-3 rounded-xl bg-red-500/10 p-4">
            <Text className="text-red-600 dark:text-red-400">❌ {errorMsg}</Text>
            <Button plain onClick={reset}>やり直す</Button>
          </div>
        )}
      </section>

      <footer className="mt-8 text-center">
        <Text className="text-xs">
          FFmpeg 2-passエンコード / palettegen+paletteuse・ファイルは24時間後に自動削除されます
        </Text>
      </footer>
    </main>
  );
}
