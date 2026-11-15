"use client";

import { useEffect, useRef, useState } from "react";

import { Episode, yawDegrees } from "@/lib/integrity";

// Same version as package.json: the WebAssembly files are loaded from the CDN at runtime.
const WASM = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.3/wasm";
const MODEL =
  "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";
const NO_FACE_MS = 5000;
const MANY_FACES_MS = 2000;
const TURNED_MS = 3000;
const TURNED_DEG = 35;

type Signal = { kind: string; at: string; duration_ms: number; detail: string };

/** Records browser signals during a test and sends them as an event log. With camera
 *  consent it also runs face detection on this device; no image or video is sent. */
export function IntegrityMonitor({ attemptId, camera }: { attemptId: number; camera: boolean }) {
  const queue = useRef<Signal[]>([]);
  const video = useRef<HTMLVideoElement>(null);
  const [cameraState, setCameraState] = useState<"off" | "starting" | "on" | "unavailable">(
    camera ? "starting" : "off",
  );

  useEffect(() => {
    const url = `/api/attempts/${attemptId}/events`;
    const push = (kind: string, duration_ms = 0, detail = "", at = Date.now() - duration_ms) =>
      queue.current.push({ kind, at: new Date(at).toISOString(), duration_ms, detail });
    const flush = () => {
      if (queue.current.length === 0) return;
      const body = JSON.stringify(queue.current.splice(0, 200));
      fetch(url, { method: "POST", body, keepalive: true, headers: { "Content-Type": "application/json" } }).catch(
        () => undefined,
      );
    };

    let hiddenAt = 0;
    let blurAt = 0;
    let wasFullscreen = !!document.fullscreenElement;
    const onVisibility = () => {
      if (document.hidden) hiddenAt = Date.now();
      else if (hiddenAt) push("tab_hidden", Date.now() - hiddenAt);
    };
    const onBlur = () => (blurAt = Date.now());
    const onFocus = () => blurAt && push("window_blur", Date.now() - blurAt);
    const onFullscreen = () => {
      if (wasFullscreen && !document.fullscreenElement) push("fullscreen_exit");
      wasFullscreen = !!document.fullscreenElement;
    };
    const onCopy = () => push("copy", 0, `${String(window.getSelection() ?? "").length} characters`);
    const onPaste = (e: ClipboardEvent) =>
      push("paste", 0, `${e.clipboardData?.getData("text").length ?? 0} characters`);

    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", onFocus);
    document.addEventListener("fullscreenchange", onFullscreen);
    document.addEventListener("copy", onCopy);
    document.addEventListener("paste", onPaste);
    window.addEventListener("pagehide", flush);
    const timer = window.setInterval(flush, 10_000);

    let stop = () => {};
    if (camera) {
      stop = watchFaces(video, push, setCameraState);
    }
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("fullscreenchange", onFullscreen);
      document.removeEventListener("copy", onCopy);
      document.removeEventListener("paste", onPaste);
      window.removeEventListener("pagehide", flush);
      window.clearInterval(timer);
      stop();
      flush();
    };
  }, [attemptId, camera]);

  return (
    <div className="flex items-center gap-3 text-xs text-muted-foreground" aria-live="polite">
      {camera && (
        <video ref={video} muted playsInline className="h-12 w-16 rounded border object-cover" aria-label="Your camera, seen only on this device" />
      )}
      <span>
        {cameraState === "on" && "Camera checks are running on this device. No images are sent."}
        {cameraState === "starting" && "Starting camera checks…"}
        {cameraState === "unavailable" && "Camera checks could not start; this is noted for your instructor."}
        {cameraState === "off" && "Browser signals (tab switches, copy and paste) are recorded."}
      </span>
    </div>
  );
}

function watchFaces(
  video: React.RefObject<HTMLVideoElement | null>,
  push: (kind: string, duration_ms?: number, detail?: string, at?: number) => void,
  setState: (s: "on" | "unavailable") => void,
): () => void {
  let stopped = false;
  let timer = 0;
  let stream: MediaStream | null = null;
  const noFace = new Episode(NO_FACE_MS);
  const many = new Episode(MANY_FACES_MS);
  const turned = new Episode(TURNED_MS);
  const report = (kind: string, ms: number | null, t: number) => ms !== null && push(kind, ms, "", t - ms);

  (async () => {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 } });
      const el = video.current;
      if (stopped || !el) return;
      el.srcObject = stream;
      await el.play();
      const { FaceLandmarker, FilesetResolver } = await import("@mediapipe/tasks-vision");
      const files = await FilesetResolver.forVisionTasks(WASM);
      const landmarker = await FaceLandmarker.createFromOptions(files, {
        baseOptions: { modelAssetPath: MODEL },
        runningMode: "VIDEO",
        numFaces: 2,
        outputFacialTransformationMatrixes: true,
      });
      if (stopped) return;
      setState("on");
      timer = window.setInterval(() => {
        const t = Date.now();
        const result = landmarker.detectForVideo(el, performance.now());
        const faces = result.faceLandmarks.length;
        const matrix = result.facialTransformationMatrixes?.[0];
        report("no_face", noFace.update(faces === 0, t), t);
        report("multiple_faces", many.update(faces > 1, t), t);
        report("head_turned", turned.update(!!matrix && yawDegrees(matrix.data) > TURNED_DEG, t), t);
      }, 500);
    } catch {
      if (!stopped) {
        push("camera_unavailable");
        setState("unavailable");
      }
    }
  })();

  return () => {
    stopped = true;
    window.clearInterval(timer);
    const t = Date.now();
    report("no_face", noFace.end(t), t);
    report("multiple_faces", many.end(t), t);
    report("head_turned", turned.end(t), t);
    stream?.getTracks().forEach((track) => track.stop());
  };
}
