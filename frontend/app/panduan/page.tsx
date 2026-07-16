"use client";

import { useState } from "react";
import Link from "next/link";

interface Step {
  title: string;
  icon: string;        // svg path(s)
  body: React.ReactNode;
}

const STEPS: Step[] = [
  {
    title: "Selamat datang",
    icon: "M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z",
    body: (
      <>
        Aplikasi ini memperkirakan <b>cutting (serpihan batuan)</b> pada shale shaker dari video
        memakai segmentasi citra. Panduan singkat ini menuntun Anda dari mengunggah video hingga
        membaca laporan. Anda bisa <b>melewati</b> kapan saja dan langsung mencoba.
      </>
    ),
  },
  {
    title: "1 · Pilih Video",
    icon: "M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4 M17 8l-5-5-5 5 M12 3v12",
    body: (
      <>
        Di menu <b>Dashboard</b>, Anda bisa <b>unggah video sendiri</b> (mp4) melalui area upload, atau
        langsung klik salah satu <b>video sumber</b> yang telah disediakan sebagai bahan uji coba.
        Frame pertama akan otomatis tampil sebagai acuan untuk mengatur area deteksi.
      </>
    ),
  },
  {
    title: "2 · Tentukan Area ROI",
    icon: "M3 3h7v7H3z M14 3h7v7h-7z M14 14h7v7h-7z M3 14h7v7H3z",
    body: (
      <>
        Geser <b>4 titik sudut</b> (TL, TR, BR, BL) mengelilingi permukaan shale shaker yang ingin
        dipantau. Saat menggeser, muncul <b>pratinjau ter-zoom</b> agar posisi titik presisi.
      </>
    ),
  },
  {
    title: "3 · Atur Konfigurasi (Settings)",
    icon: "M12 15a3 3 0 100-6 3 3 0 000 6z M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z",
    body: (
      <>
        Pilih <b>model</b> &amp; <b>threshold</b>, atur <b>stride</b> (kecepatan), serta parameter
        <b> grid coverage</b>. Tersedia <b>dua tombol setelan terbaik</b> (MobileViT &amp; BiSeNet v2)
        untuk konfigurasi rekomendasi sekali klik, dan ikon <b>&quot;i&quot;</b> di tiap parameter +
        pratinjau interaktif yang memperlihatkan efek tiap slider.
      </>
    ),
  },
  {
    title: "4 · Mulai Deteksi Live",
    icon: "M5 3l14 9-14 9V3z",
    body: (
      <>
        Klik <b>Start Deteksi Live</b>. Tampilan bersifat <b>frame-accurate</b>: frame yang ditampilkan
        selalu cocok dengan mask deteksinya. Panel <b>Last Value</b> menampilkan coverage% terkini,
        beserta jumlah stone &amp; FPS.
      </>
    ),
  },
  {
    title: "5 · Jeda, Stop & Simpan Otomatis",
    icon: "M6 5h4v14H6zM14 5h4v14h-4z",
    body: (
      <>
        Gunakan <b>Jeda/Lanjut</b> untuk menjeda (deteksi backend ikut berhenti). <b>Stop</b>
        membatalkan sesi. Saat video selesai, hasil <b>tersimpan otomatis</b> (DB + CSV) dan tampilan
        kembali ke kondisi awal untuk sesi berikutnya.
      </>
    ),
  },
  {
    title: "6 · Riwayat & Laporan",
    icon: "M3 3v5h5 M3.05 13A9 9 0 106 5.3L3 8 M12 7v5l4 2",
    body: (
      <>
        Buka menu <b>Riwayat</b> untuk melihat ringkasan tiap sesi, grafik tren Coverage % &amp; Stone,
        serta mengunduh laporan <b>CSV</b> dan <b>PDF profesional</b>. Sesi dapat dihapus bila perlu.
      </>
    ),
  },
];

export default function PanduanPage() {
  const [step, setStep] = useState(0);
  const total = STEPS.length;
  const isLast = step === total - 1;
  const s = STEPS[step];

  return (
    <div className="h-full overflow-y-auto p-4 md:p-6">
      <div className="max-w-3xl mx-auto">
        {/* Top bar: progress + skip */}
        <div className="flex items-center justify-between mb-4">
          <span className="text-xs font-medium text-slate-500">Langkah {step + 1} dari {total}</span>
          <Link href="/" className="text-xs text-slate-500 hover:text-brand transition-colors">
            Lewati panduan &amp; mulai →
          </Link>
        </div>

        {/* Progress bar */}
        <div className="h-1.5 w-full rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden mb-6">
          <div className="h-full bg-brand transition-all duration-300" style={{ width: `${((step + 1) / total) * 100}%` }} />
        </div>

        {/* Step card */}
        <div className="card min-h-[280px] flex flex-col">
          <div className="flex items-center gap-4">
            <div className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-brand-light text-brand">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d={s.icon} />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-slate-800 dark:text-slate-100">{s.title}</h1>
          </div>
          <p className="text-slate-600 dark:text-slate-300 mt-5 leading-relaxed text-[15px]">{s.body}</p>

          {/* Step dots */}
          <div className="flex items-center gap-1.5 mt-auto pt-6">
            {STEPS.map((_, i) => (
              <button
                key={i}
                onClick={() => setStep(i)}
                aria-label={`Langkah ${i + 1}`}
                className={`h-2 rounded-full transition-all ${i === step ? "w-6 bg-brand" : "w-2 bg-slate-300 dark:bg-slate-600 hover:bg-brand/50"}`}
              />
            ))}
          </div>
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between mt-5">
          <button
            onClick={() => setStep((v) => Math.max(0, v - 1))}
            disabled={step === 0}
            className="btn-muted disabled:opacity-40"
          >
            ← Sebelumnya
          </button>

          {isLast ? (
            <Link href="/" className="btn-primary inline-flex items-center gap-1.5">
              Mulai Menggunakan Aplikasi
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14 M12 5l7 7-7 7" /></svg>
            </Link>
          ) : (
            <button onClick={() => setStep((v) => Math.min(total - 1, v + 1))} className="btn-primary inline-flex items-center gap-1.5">
              Berikutnya
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 18l6-6-6-6" /></svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
