// Extract the first frame of a selected video file entirely in the browser,
// to (1) prove the upload/selection succeeded and (2) provide a still image at
// native resolution for ROI drawing (coords map to full-frame pixels).

export interface ExtractedFrame {
  dataUrl: string;   // full-res JPEG (for crisp ROI editing display)
  thumbUrl: string;  // small JPEG for localStorage (Settings preview)
  width: number;     // natural video width (px)
  height: number;    // natural video height (px)
}

export function extractFirstFrame(file: File): Promise<ExtractedFrame> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "auto";
    video.muted = true;
    (video as HTMLVideoElement).playsInline = true;
    video.src = url;

    const cleanup = () => URL.revokeObjectURL(url);

    video.onloadeddata = () => {
      try {
        video.currentTime = Math.min(0.1, (video.duration || 1) / 2);
      } catch {
        /* some browsers fire seeked without explicit seek */
      }
    };

    video.onseeked = () => {
      try {
        const w = video.videoWidth, h = video.videoHeight;
        const canvas = document.createElement("canvas");
        canvas.width = w; canvas.height = h;
        const ctx = canvas.getContext("2d");
        if (!ctx) throw new Error("canvas tidak tersedia");
        ctx.drawImage(video, 0, 0, w, h);
        const dataUrl = canvas.toDataURL("image/jpeg", 0.85);

        const tw = 480;
        const th = Math.max(1, Math.round(h * (tw / w)));
        const tcanvas = document.createElement("canvas");
        tcanvas.width = tw; tcanvas.height = th;
        tcanvas.getContext("2d")?.drawImage(video, 0, 0, tw, th);
        const thumbUrl = tcanvas.toDataURL("image/jpeg", 0.7);

        cleanup();
        resolve({ dataUrl, thumbUrl, width: w, height: h });
      } catch (e) {
        cleanup();
        reject(e);
      }
    };

    video.onerror = () => {
      cleanup();
      reject(new Error("Gagal membaca video, format mungkin tidak didukung browser."));
    };
  });
}

// Convert a data URL back into a File (for the ROI preview API on Settings).
export async function dataUrlToFile(dataUrl: string, name = "frame.jpg"): Promise<File> {
  const res = await fetch(dataUrl);
  const blob = await res.blob();
  return new File([blob], name, { type: blob.type || "image/jpeg" });
}
