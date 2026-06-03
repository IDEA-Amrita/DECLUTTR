import { useState, useEffect, useRef } from "react";
import { api } from "../lib/api";

interface ScanStatus {
  status: string;
  progress: number;
  duplicates_found: number;
}

interface DriveFile {
  id: string;
  drive_file_id: string;
  name: string;
  mime_type: string;
  size_bytes: number;
  category: string;
  is_flagged: number;
  description: string | null;
  ai_reason: string | null;
  in_deletion_list: number;
}

const fmt = (bytes: number) => {
  if (bytes > 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes > 1e6) return `${(bytes / 1e6).toFixed(1)} MB`;
  return `${(bytes / 1e3).toFixed(0)} KB`;
};

const CATEGORIES = ["duplicate", "large", "old", "screenshot", "unused"];

export default function GDrivePage() {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [linked, setLinked] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [scanId, setScanId] = useState<string | null>(null);
  const [scan, setScan] = useState<ScanStatus | null>(null);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [activeCategory, setActiveCategory] = useState("duplicate");
  const [paradigm, setParadigm] = useState("type");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [deletionConsent, setDeletionConsent] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api.getDriveAuthStatus().then(d => {
      setLinked(d.linked);
      setEmail(d.email);
    });
    const params = new URLSearchParams(window.location.search);
    if (params.get("linked") === "1") {
      setMessage("✓ Google Drive linked successfully");
      window.history.replaceState({}, "", "/gdrive");
      api.getDriveAuthStatus().then(d => { setLinked(d.linked); setEmail(d.email); });
    }
  }, []);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

const linkAccount = () => {
  api.getDriveAuthUrl().then(d => {
    const opener = (window as any).electron?.openExternal;
    if (opener) {
      opener(d.auth_url);
    } else {
      window.open(d.auth_url, "_blank");
    }
  });
};
  const startScan = async () => {
    setLoading(true);
    setMessage("");
    const res = await api.startDriveScan();
    setScanId(res.scan_id);
    setLoading(false);
    setScan({ status: "pending", progress: 0, duplicates_found: 0 });
    pollRef.current = setInterval(async () => {
      const s = await api.getDriveScanStatus(res.scan_id);
      setScan(s);
      if (s.status === "done" || s.status === "error") {
        clearInterval(pollRef.current!);
        if (s.status === "done") {
          const f = await api.getDriveFiles(res.scan_id);
          setFiles(f);
        }
      }
    }, 1500);
  };

  const flagFile = async (fileId: string, description: string) => {
    await api.flagDriveFile(fileId, description);
    setFiles(prev => prev.map(f => f.drive_file_id === fileId ? { ...f, is_flagged: 1, description } : f));
  };

  const organise = async () => {
    if (!scanId) return;
    setLoading(true);
    await api.organiseDrive(scanId, paradigm);
    setLoading(false);
    setMessage("✓ Files organised into folders.");
  };

  const executeDeletions = async () => {
    if (!scanId || !deletionConsent) return;
    setLoading(true);
    const res = await api.approveDriveDeletion(scanId);
    setLoading(false);
    setMessage(`✓ ${res.deleted} files moved to Drive Trash.`);
    setDeletionConsent(false);
  };

  const filteredFiles = files.filter(f => f.category === activeCategory);
  const deletionList = files.filter(f => f.in_deletion_list === 1);
  const categoryCounts = Object.fromEntries(CATEGORIES.map(c => [c, files.filter(f => f.category === c).length]));

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Google Drive Cleanup</h1>
          <p className="text-gray-400 text-sm mt-1">Privacy-first cloud declutter</p>
        </div>
        {email && (
          <span className="text-xs bg-green-900/40 text-green-300 px-3 py-1 rounded-full border border-green-700">
            ✓ {email}
          </span>
        )}
      </div>

      {/* Step bar */}
      <div className="flex items-center gap-2">
        {["Scan & auto-clean", "Review & flag", "Organise & delete"].map((label, i) => {
          const n = i + 1;
          return (
            <div key={n} className="flex items-center flex-1 last:flex-none">
              <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium
                ${step === n ? "bg-blue-600 text-white" : step > n ? "text-green-400" : "text-gray-500"}`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs
                  ${step === n ? "bg-white text-blue-600" : step > n ? "bg-green-500 text-white" : "bg-gray-600 text-gray-400"}`}>
                  {step > n ? "✓" : n}
                </span>
                {label}
              </div>
              {i < 2 && <div className="flex-1 h-px bg-gray-700 mx-2" />}
            </div>
          );
        })}
      </div>

      {message && (
        <div className="bg-green-900/30 border border-green-700 rounded-lg p-3 text-green-300 text-sm">{message}</div>
      )}

      {/* Step 1 */}
      {step === 1 && (
        <div className="space-y-4">
          {!linked ? (
            <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 text-center space-y-4">
              <p className="text-gray-300">Connect your Google Drive to start cleaning.</p>
              <button onClick={linkAccount}
                className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-2.5 rounded-lg font-medium transition">
                Link Google Drive
              </button>
            </div>
          ) : (
            <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-white font-medium">Scan your Drive</h2>
                  <p className="text-gray-400 text-sm">Only file names, sizes, and dates are read. No file contents.</p>
                </div>
                <button onClick={startScan} disabled={loading || scan?.status === "running"}
                  className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-5 py-2 rounded-lg font-medium transition">
                  {scan?.status === "running" ? "Scanning…" : "Start scan"}
                </button>
              </div>

              {scan && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm text-gray-400">
                    <span>{scan.progress}% complete</span>
                    <span className="capitalize">{scan.status}</span>
                  </div>
                  <div className="w-full bg-gray-700 rounded-full h-2">
                    <div className="bg-blue-500 h-2 rounded-full transition-all" style={{ width: `${scan.progress}%` }} />
                  </div>
                  {scan.status === "done" && (
                    <div className="grid grid-cols-2 gap-3 mt-3">
                      <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                        <p className="text-lg font-semibold text-yellow-300">{scan.duplicates_found}</p>
                        <p className="text-gray-400 text-xs mt-0.5">Duplicates found</p>
                      </div>
                      <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                        <p className="text-lg font-semibold text-white">{files.length}</p>
                        <p className="text-gray-400 text-xs mt-0.5">Total files</p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {scan?.status === "done" && (
                <button onClick={() => setStep(2)}
                  className="w-full bg-gray-700 hover:bg-gray-600 text-white py-2.5 rounded-lg font-medium transition">
                  Continue to review →
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Step 2 */}
      {step === 2 && (
        <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-white font-medium">Review & flag</h2>
              <p className="text-gray-400 text-sm">Star files to keep and protect similar ones.</p>
            </div>
            <button onClick={() => setStep(3)}
              className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition">
              Done reviewing →
            </button>
          </div>

          <div className="flex gap-2 flex-wrap">
            {CATEGORIES.map(cat => (
              <button key={cat} onClick={() => setActiveCategory(cat)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition capitalize
                  ${activeCategory === cat ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-300 hover:bg-gray-600"}`}>
                {cat} ({categoryCounts[cat] || 0})
              </button>
            ))}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[480px] overflow-y-auto pr-1">
            {filteredFiles.length === 0 && (
              <p className="text-gray-500 text-sm col-span-2 py-8 text-center">No files in this category.</p>
            )}
            {filteredFiles.map(f => (
              <FileCard key={f.id} file={f} onFlag={flagFile} />
            ))}
          </div>
        </div>
      )}

      {/* Step 3 */}
      {step === 3 && (
        <div className="space-y-4">
          <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 space-y-4">
            <h2 className="text-white font-medium">Organise your Drive</h2>
            <div className="grid grid-cols-2 gap-3">
              {[
                { key: "type", label: "By file type", desc: "Images/, Videos/, Docs/" },
                { key: "date", label: "By date", desc: "2024-03/, 2024-04/" },
                { key: "personal_professional", label: "Personal / Professional", desc: "Context-aware split" },
                { key: "usage_age", label: "By usage age", desc: "Recent / Archive" },
              ].map(p => (
                <label key={p.key}
                  className={`p-4 rounded-xl border cursor-pointer transition
                    ${paradigm === p.key ? "border-blue-500 bg-blue-900/20" : "border-gray-600 hover:border-gray-500"}`}>
                  <input type="radio" name="paradigm" value={p.key}
                    checked={paradigm === p.key} onChange={() => setParadigm(p.key)} className="sr-only" />
                  <p className="text-white font-medium text-sm">{p.label}</p>
                  <p className="text-gray-400 text-xs font-mono mt-1">{p.desc}</p>
                </label>
              ))}
            </div>
            <button onClick={organise} disabled={loading}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-5 py-2.5 rounded-lg font-medium transition">
              {loading ? "Organising…" : "Create folders & move files"}
            </button>
          </div>

          {deletionList.length > 0 && (
            <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="text-white font-medium">
                  Deletion list
                  <span className="ml-2 bg-red-900/40 text-red-300 text-xs px-2 py-0.5 rounded-full border border-red-700">
                    {deletionList.length} files · {fmt(deletionList.reduce((s, f) => s + f.size_bytes, 0))}
                  </span>
                </h2>
                <button onClick={() => document.getElementById("del-details")?.classList.toggle("hidden")}
                  className="text-sm text-gray-400 hover:text-gray-300">Show / hide</button>
              </div>
              <div id="del-details" className="hidden space-y-1.5 max-h-48 overflow-y-auto">
                {deletionList.map(f => (
                  <div key={f.id} className="flex items-center justify-between text-sm bg-gray-700/50 rounded px-3 py-1.5">
                    <span className="text-gray-300 truncate max-w-xs">{f.name}</span>
                    <span className="text-gray-500 ml-2">{fmt(f.size_bytes)}</span>
                  </div>
                ))}
              </div>
              <div className="border border-red-800/50 bg-red-900/10 rounded-lg p-4 space-y-3">
                <label className="flex items-start gap-3 cursor-pointer">
                  <input type="checkbox" checked={deletionConsent}
                    onChange={e => setDeletionConsent(e.target.checked)} className="mt-0.5 accent-red-500" />
                  <span className="text-red-200 text-sm">
                    Move {deletionList.length} files to Drive Trash. Restorable within 30 days.
                  </span>
                </label>
                <button onClick={executeDeletions} disabled={!deletionConsent || loading}
                  className="bg-red-700 hover:bg-red-600 disabled:opacity-40 text-white px-5 py-2.5 rounded-lg font-medium transition">
                  {loading ? "Deleting…" : `Delete ${deletionList.length} files`}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function FileCard({ file, onFlag }: { file: DriveFile; onFlag: (id: string, desc: string) => void }) {
  const [desc, setDesc] = useState(file.description || "");
  const [showDesc, setShowDesc] = useState(false);

  return (
    <div className={`bg-gray-700/40 rounded-xl p-3 border transition
      ${file.is_flagged ? "border-green-600" : "border-gray-600"}`}>
      <div className="flex gap-3">
        <div className="w-14 h-14 rounded-lg bg-gray-600 shrink-0 flex items-center justify-center text-2xl">
          {mimeIcon(file.mime_type)}
        </div>
        <div className="flex-1 min-w-0 space-y-1">
          <p className="text-white text-sm font-medium truncate">{file.name}</p>
          <p className="text-gray-400 text-xs">{fmt(file.size_bytes)}</p>
          {file.ai_reason && <p className="text-gray-400 text-xs italic">{file.ai_reason}</p>}
        </div>
      </div>
      <div className="mt-3">
        <button onClick={() => setShowDesc(!showDesc)}
          className={`w-full py-1.5 rounded-lg text-xs font-medium transition border
            ${file.is_flagged ? "bg-green-700 border-green-600 text-white" : "bg-gray-600 border-gray-500 text-gray-200 hover:bg-gray-500"}`}>
          {file.is_flagged ? "⭐ Flagged to keep" : "⭐ Keep & protect similar"}
        </button>
        {showDesc && (
          <div className="mt-2 space-y-1.5">
            <input value={desc} onChange={e => setDesc(e.target.value)}
              placeholder="Describe this file to protect similar ones"
              className="w-full bg-gray-600 border border-gray-500 rounded px-2 py-1.5 text-xs text-white placeholder-gray-400 focus:outline-none focus:border-blue-500" />
            <button onClick={() => { onFlag(file.drive_file_id, desc); setShowDesc(false); }}
              className="w-full bg-green-700 hover:bg-green-600 text-white text-xs py-1.5 rounded-lg transition font-medium">
              Save & protect
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function mimeIcon(mime: string): string {
  if (mime.startsWith("image/")) return "🖼";
  if (mime.startsWith("video/")) return "🎬";
  if (mime.startsWith("audio/")) return "🎵";
  if (mime.includes("pdf")) return "📄";
  if (mime.includes("spreadsheet") || mime.includes("excel")) return "📊";
  if (mime.includes("zip") || mime.includes("archive")) return "🗜";
  return "📁";
}