import React from "react";
import ReactDOM from "react-dom/client";
import QRCode from "qrcode";
import {
  ArrowDownToLine,
  BarChart3,
  CheckCircle2,
  FileText,
  Languages,
  Loader2,
  Smartphone,
  RefreshCcw,
  Upload,
} from "lucide-react";
import "./styles.css";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

type Analysis = {
  来源?: "ai" | "local";
  标准摘要?: Record<string, unknown>;
  报告修改建议与解决方案?: Record<string, unknown>;
  最新数据补充与核验清单?: unknown[];
  同类企业对比与业务建议?: Record<string, unknown>;
  精读结论?: Record<string, unknown>;
  经济测算专项审查?: Record<string, unknown>;
  输出完整性检查?: Record<string, unknown>;
  关键词?: Array<string | [string, number]>;
  语言?: string;
};

type Report = {
  id: number;
  filename: string;
  mime_type?: string;
  file_size: number;
  status: string;
  language: string;
  parser_notes: string;
  extracted_text?: string;
  analysis?: Analysis | null;
  created_at: string;
};

type Comparison = {
  id: number;
  report_ids: number[];
  result: Record<string, unknown>;
};

type AccessInfo = {
  local_ips: string[];
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function App() {
  const [reports, setReports] = React.useState<Report[]>([]);
  const [activeId, setActiveId] = React.useState<number | null>(null);
  const [selectedIds, setSelectedIds] = React.useState<number[]>([]);
  const [comparison, setComparison] = React.useState<Comparison | null>(null);
  const [mobileUrl, setMobileUrl] = React.useState<string>("");
  const [mobileQr, setMobileQr] = React.useState<string>("");
  const [busy, setBusy] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const active = reports.find((report) => report.id === activeId) ?? reports[0] ?? null;

  async function refresh() {
    const data = await api<{ reports: Report[] }>("/api/reports");
    setReports(data.reports);
    if (!activeId && data.reports[0]) setActiveId(data.reports[0].id);
  }

  React.useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  React.useEffect(() => {
    async function loadMobileAccess() {
      const data = await api<AccessInfo>("/api/access-info");
      const hostname = window.location.hostname;
      const port = window.location.port ? `:${window.location.port}` : "";
      const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
      const accessHost = isLocalhost ? data.local_ips[0] : hostname;
      if (!accessHost) return;
      const nextUrl = `${window.location.protocol}//${accessHost}${port}/`;
      setMobileUrl(nextUrl);
      setMobileQr(
        await QRCode.toDataURL(nextUrl, {
          errorCorrectionLevel: "M",
          margin: 1,
          width: 180,
          color: {
            dark: "#152033",
            light: "#ffffff",
          },
        }),
      );
    }
    loadMobileAccess().catch(() => {
      setMobileUrl("");
      setMobileQr("");
    });
  }, []);

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setBusy("upload");
    setError(null);
    const form = new FormData();
    Array.from(files).forEach((file) => form.append("files", file));
    try {
      const data = await api<{ reports: Report[] }>("/api/reports/upload", { method: "POST", body: form });
      await refresh();
      if (data.reports[0]) setActiveId(data.reports[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setBusy(null);
    }
  }

  async function analyze(reportId: number) {
    setBusy(`analyze-${reportId}`);
    setError(null);
    try {
      const updated = await api<Report>(`/api/reports/${reportId}/analyze`, { method: "POST" });
      setReports((current) => current.map((report) => (report.id === updated.id ? updated : report)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "分析失败");
    } finally {
      setBusy(null);
    }
  }

  async function compare() {
    setBusy("compare");
    setError(null);
    try {
      const result = await api<Comparison>("/api/reports/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ report_ids: selectedIds }),
      });
      setComparison(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "对比失败");
    } finally {
      setBusy(null);
    }
  }

  function toggleSelected(id: number) {
    setSelectedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>可研报告精读工具</h1>
          <p>本机运行，文件与结果保存在本地；配置 API key 后启用 AI 精读。</p>
        </div>
        <button className="icon-button" onClick={() => refresh()} title="刷新">
          <RefreshCcw size={18} />
        </button>
      </header>

      <section className="upload-band">
        <label className="upload-target">
          {busy === "upload" ? <Loader2 className="spin" size={28} /> : <Upload size={28} />}
          <span>上传 Word、PDF、图片报告</span>
          <input type="file" multiple accept=".doc,.docx,.pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp" onChange={(event) => upload(event.target.files)} />
        </label>
        <div className="local-note">
          <CheckCircle2 size={18} />
          <span>PC 浏览器访问 127.0.0.1；手机同 Wi-Fi 访问电脑局域网 IP。</span>
        </div>
        <div className="qr-card">
          <div className="qr-meta">
            <Smartphone size={18} />
            <div>
              <strong>手机扫码访问</strong>
              <a href={mobileUrl || "#"}>{mobileUrl || "正在获取本机地址..."}</a>
            </div>
          </div>
          {mobileQr ? <img src={mobileQr} alt="手机访问二维码" /> : <div className="qr-placeholder" />}
        </div>
      </section>

      {error && <div className="error-line">{error}</div>}

      <section className="workspace">
        <aside className="report-list">
          <div className="panel-title">
            <FileText size={18} />
            <span>报告</span>
          </div>
          {reports.length === 0 && <p className="empty">还没有上传报告。</p>}
          {reports.map((report) => (
            <button
              key={report.id}
              className={`report-row ${active?.id === report.id ? "active" : ""}`}
              onClick={() => setActiveId(report.id)}
            >
              <input
                aria-label="选择用于对比"
                type="checkbox"
                checked={selectedIds.includes(report.id)}
                onChange={(event) => {
                  event.stopPropagation();
                  toggleSelected(report.id);
                }}
                onClick={(event) => event.stopPropagation()}
              />
              <span className="report-name">{report.filename}</span>
              <span className={`status status-${report.status}`}>{statusText(report.status)}</span>
            </button>
          ))}
          <button className="primary-action" disabled={selectedIds.length < 2 || busy === "compare"} onClick={compare}>
            {busy === "compare" ? <Loader2 className="spin" size={18} /> : <BarChart3 size={18} />}
            <span>交叉比对</span>
          </button>
        </aside>

        <section className="detail-panel">
          {active ? (
            <>
              <div className="detail-head">
                <div>
                  <h2>{active.filename}</h2>
                  <p>{active.parser_notes || "已上传，等待解析说明。"}</p>
                </div>
                <div className="actions">
                  <button className="secondary-action" disabled={busy === `analyze-${active.id}`} onClick={() => analyze(active.id)}>
                    {busy === `analyze-${active.id}` ? <Loader2 className="spin" size={18} /> : <Languages size={18} />}
                    <span>生成精读</span>
                  </button>
                  <a className="secondary-action" href={`${API_BASE}/api/reports/${active.id}/export`}>
                    <ArrowDownToLine size={18} />
                    <span>导出 Word</span>
                  </a>
                </div>
              </div>
              <AnalysisView analysis={active.analysis} language={active.language} />
              <TextPreview text={active.extracted_text ?? ""} />
            </>
          ) : (
            <div className="empty detail-empty">上传报告后开始精读。</div>
          )}
        </section>
      </section>

      {comparison && (
        <section className="comparison-band">
          <div className="detail-head">
            <div>
              <h2>跨报告交叉比对</h2>
              <p>一致性信号、矛盾点和预期差地图。</p>
            </div>
            <a className="secondary-action" href={`${API_BASE}/api/comparisons/${comparison.id}/export`}>
              <ArrowDownToLine size={18} />
              <span>导出对比 Word</span>
            </a>
          </div>
          <ObjectView value={comparison.result} />
        </section>
      )}
    </main>
  );
}

function AnalysisView({ analysis, language }: { analysis?: Analysis | null; language: string }) {
  if (!analysis) {
    return <div className="empty">尚未生成分析。点击“生成精读”后会输出报告修改建议、经济测算专项审查、最新数据核验和关键词。</div>;
  }
  return (
    <div className="analysis-grid">
      <section>
        <h3>标准摘要</h3>
        <ObjectView value={analysis.标准摘要 ?? {}} />
      </section>
      <section>
        <h3>报告修改建议与解决方案</h3>
        <ObjectView value={analysis.报告修改建议与解决方案 ?? {}} />
      </section>
      <section>
        <h3>最新数据补充与核验清单</h3>
        <ObjectView value={analysis.最新数据补充与核验清单 ?? []} />
      </section>
      <section>
        <h3>同类企业对比与业务建议</h3>
        <ObjectView value={analysis.同类企业对比与业务建议 ?? {}} />
      </section>
      <section>
        <h3>经济测算专项审查</h3>
        <ObjectView value={analysis.经济测算专项审查 ?? {}} />
      </section>
      <section>
        <h3>精读结论</h3>
        <ObjectView value={analysis.精读结论 ?? {}} />
      </section>
      <section>
        <h3>输出完整性检查</h3>
        <ObjectView value={analysis.输出完整性检查 ?? {}} />
      </section>
      <section className="wide">
        <h3>英文报告全文翻译</h3>
        <ObjectView value={(analysis as Record<string, unknown>).英文报告全文翻译 ?? "非英文报告，无需全文翻译。"} />
      </section>
      <section className="wide">
        <h3>关键词</h3>
        <div className="chips">
          {(analysis.关键词 ?? []).map((item, index) => (
            <span key={index}>{Array.isArray(item) ? item[0] : item}</span>
          ))}
        </div>
        <p className="source-line">语言：{analysis.语言 ?? language} · 分析来源：{analysis.来源 === "ai" ? "AI" : "未标注"}</p>
      </section>
    </div>
  );
}

function ObjectView({ value }: { value: unknown }) {
  if (Array.isArray(value)) {
    return (
      <ul className="clean-list">
        {value.map((item, index) => (
          <li key={index}>{typeof item === "object" ? <ObjectView value={item} /> : String(item)}</li>
        ))}
      </ul>
    );
  }
  if (value && typeof value === "object") {
    return (
      <div className="kv-list">
        {Object.entries(value as Record<string, unknown>).map(([key, val]) => (
          <div className="kv-row" key={key}>
            <span className="kv-key">{key}</span>
            <div className="kv-value"><ObjectView value={val} /></div>
          </div>
        ))}
      </div>
    );
  }
  return <span>{String(value || "无")}</span>;
}

function TextPreview({ text }: { text: string }) {
  return (
    <section className="text-preview">
      <h3>解析文本预览</h3>
      <pre>{text.slice(0, 6000) || "暂无可预览文本。"}</pre>
    </section>
  );
}

function statusText(status: string) {
  const map: Record<string, string> = {
    parsed: "已解析",
    analyzed: "已精读",
    parse_failed: "解析失败",
  };
  return map[status] ?? status;
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
