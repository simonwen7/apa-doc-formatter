import { useState } from "react";
import "./App.css";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD ? "" : "http://127.0.0.1:8000");

const TEMPLATE_OPTIONS = [
  {
    id: "apa7_student",
    label: "APA 7 Student Paper",
  },
];

function App() {
  const [file, setFile] = useState(null);
  const [templateId, setTemplateId] = useState(TEMPLATE_OPTIONS[0].id);
  const [loading, setLoading] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [fixResult, setFixResult] = useState(null);
  const [error, setError] = useState("");

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0] || null;
    setFile(selected);
    setAnalyzeResult(null);
    setFixResult(null);
    setError("");
  };

  const handleAnalyze = async () => {
    if (!file) {
      setError("Please choose a .docx file first.");
      return;
    }

    setLoading(true);
    setError("");
    setAnalyzeResult(null);
    setFixResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("template_id", templateId);

      const res = await fetch(`${API_BASE}/documents/analyze`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(
          data?.detail
            ? typeof data.detail === "string"
              ? data.detail
              : JSON.stringify(data.detail)
            : `Analyze failed: ${res.status}`
        );
      }

      setAnalyzeResult(data);
    } catch (err) {
      setError(err.message || "Analyze request failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleFix = async () => {
    if (!file) {
      setError("Please choose a .docx file first.");
      return;
    }

    setLoading(true);
    setError("");
    setFixResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("template_id", templateId);

      const res = await fetch(`${API_BASE}/documents/fix`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(
          data?.detail
            ? typeof data.detail === "string"
              ? data.detail
              : JSON.stringify(data.detail)
            : `Fix failed: ${res.status}`
        );
      }

      setFixResult(data);
    } catch (err) {
      setError(err.message || "Fix request failed.");
    } finally {
      setLoading(false);
    }
  };

  const getDownloadUrl = () => {
    if (!fixResult?.download_url) return null;
    return `${API_BASE}${fixResult.download_url}`;
  };

  return (
    <div className="container">
      <h1>DOC Formatter Frontend</h1>
      <p>Upload a .docx file, analyze formatting, then fix and download it.</p>

      <div className="card">
        <label className="label">Choose .docx file</label>
        <input type="file" accept=".docx" onChange={handleFileChange} />

        <label className="label" style={{ marginTop: "16px" }}>
          Template
        </label>
        <select
          value={templateId}
          onChange={(e) => setTemplateId(e.target.value)}
        >
          {TEMPLATE_OPTIONS.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>

        <div className="buttonRow">
          <button onClick={handleAnalyze} disabled={loading}>
            {loading ? "Working..." : "Analyze"}
          </button>
          <button onClick={handleFix} disabled={loading}>
            {loading ? "Working..." : "Fix"}
          </button>
        </div>

        {file && (
          <p className="fileInfo">
            Selected file: <strong>{file.name}</strong>
          </p>
        )}

        {error && <div className="error">{error}</div>}
      </div>

      {analyzeResult && (
        <div className="card">
          <h2>Analyze Result</h2>
          <p>
            <strong>Filename:</strong> {analyzeResult.filename}
          </p>
          <p>
            <strong>Template:</strong> {analyzeResult.template}
          </p>
          <p>
            <strong>Score:</strong> {analyzeResult.summary?.score}
          </p>
          <p>
            <strong>Issue Count:</strong> {analyzeResult.summary?.issue_count}
          </p>

          {analyzeResult.issues?.length > 0 && (
            <>
              <h3>Issues</h3>
              <ul>
                {analyzeResult.issues.map((issue, index) => (
                  <li key={index}>
                    <strong>{issue.category}:</strong> {issue.message}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {fixResult && (
        <div className="card">
          <h2>Fix Result</h2>
          <p>
            <strong>Filename:</strong> {fixResult.filename}
          </p>
          <p>
            <strong>Template:</strong> {fixResult.template}
          </p>

          {fixResult.fixed_counts && (
            <>
              <h3>Fixed Counts</h3>
              <ul>
                {Object.entries(fixResult.fixed_counts).map(([key, value]) => (
                  <li key={key}>
                    <strong>{key}:</strong> {value}
                  </li>
                ))}
              </ul>
            </>
          )}

          {getDownloadUrl() && (
            <a href={getDownloadUrl()} target="_blank" rel="noreferrer">
              <button>Download Fixed File</button>
            </a>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
