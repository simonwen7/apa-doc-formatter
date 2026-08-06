import { useMemo, useRef, useState } from "react";
import "./Formatter.css";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD ? "" : "http://127.0.0.1:8000");

const MAX_FILE_SIZE = 10 * 1024 * 1024;

const TEMPLATE_OPTIONS = [
  {
    id: "apa7_student",
    label: "APA 7 Student Paper",
  },
];

const FIX_LABELS = {
  margins: "Document margins corrected",
  title_page_vertical_center: "Title page vertically centered",
  title_page_paragraphs_centered: "Title-page paragraphs centered",
  cover_page_leading_blanks_inserted: "Title-page spacing adjusted",
  introduction_page_break: "Introduction page break added",
  references_page_break: "References page break added",
  major_heading_spacing: "Major heading spacing corrected",
  empty_paragraphs_removed: "Unnecessary empty paragraphs removed",
  bullet_only_paragraphs_removed: "Invalid bullet-only paragraphs removed",
  intro_leading_junk_removed: "Unnecessary content before introduction removed",
  tables_touched: "Tables formatted",
  table_caption_paragraphs_touched: "Table captions formatted",
  table_title_paragraphs_touched: "Table titles formatted",
  body_paragraphs_touched: "Body paragraphs formatted",
  paragraph_indent: "Paragraph indentation corrected",
  line_spacing: "Line spacing corrected",
  space_before: "Spacing before paragraphs corrected",
  space_after: "Spacing after paragraphs corrected",
  font_name: "Font styles corrected",
  font_size: "Font sizes corrected",
  reference_entries_touched: "Reference entries formatted",
  reference_entries_rebuilt: "Reference entries rebuilt",
  reference_hanging_indent: "Reference hanging indents corrected",
  reference_line_spacing: "Reference line spacing corrected",
  reference_space_before: "Reference spacing before corrected",
  reference_space_after: "Reference spacing after corrected",
  headings_touched: "Headings formatted",
  text_normalized: "Text inconsistencies normalized",
};

function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 KB";

  const megabytes = bytes / (1024 * 1024);

  if (megabytes >= 1) {
    return `${megabytes.toFixed(2)} MB`;
  }

  return `${Math.ceil(bytes / 1024)} KB`;
}

function getFriendlyFixLabel(key) {
  if (FIX_LABELS[key]) {
    return FIX_LABELS[key];
  }

  return key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function App() {
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [templateId, setTemplateId] = useState(TEMPLATE_OPTIONS[0].id);
  const [loadingAction, setLoadingAction] = useState("");
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [fixResult, setFixResult] = useState(null);
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const isLoading = Boolean(loadingAction);

  const issueCount = Number(analyzeResult?.summary?.issue_count ?? 0);
  const score = Math.max(
    0,
    Math.min(100, Number(analyzeResult?.summary?.score ?? 0))
  );

  const groupedIssues = useMemo(() => {
    if (!analyzeResult?.issues?.length) {
      return {};
    }

    return analyzeResult.issues.reduce((groups, issue) => {
      const category = issue.category || "Other";

      if (!groups[category]) {
        groups[category] = [];
      }

      groups[category].push(issue);
      return groups;
    }, {});
  }, [analyzeResult]);

  const visibleFixedCounts = useMemo(() => {
    if (!fixResult?.fixed_counts) {
      return [];
    }

    return Object.entries(fixResult.fixed_counts)
      .filter(([, value]) => Number(value) > 0)
      .map(([key, value]) => ({
        key,
        value: Number(value),
        label: getFriendlyFixLabel(key),
      }));
  }, [fixResult]);

  const totalFixed = visibleFixedCounts.reduce(
    (total, item) => total + item.value,
    0
  );

  const getScoreLabel = () => {
    if (score >= 90) return "Excellent";
    if (score >= 70) return "Good";
    if (score >= 40) return "Needs improvement";
    return "Significant formatting changes needed";
  };

  const getScoreTone = () => {
    if (score >= 90) return "excellent";
    if (score >= 70) return "good";
    if (score >= 40) return "warning";
    return "poor";
  };

  const resetResults = () => {
    setAnalyzeResult(null);
    setFixResult(null);
    setError("");
  };

  const resetWorkflow = () => {
    setFile(null);
    setAnalyzeResult(null);
    setFixResult(null);
    setError("");
    setLoadingAction("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const selectFile = (selectedFile) => {
    if (!selectedFile) {
      return;
    }

    const isDocx = selectedFile.name.toLowerCase().endsWith(".docx");

    if (!isDocx) {
      setFile(null);
      resetResults();
      setError("Unsupported file type. Please upload a .docx file.");
      return;
    }

    if (selectedFile.size > MAX_FILE_SIZE) {
      setFile(null);
      resetResults();
      setError("This file is larger than 10 MB. Please choose a smaller file.");
      return;
    }

    setFile(selectedFile);
    resetResults();
  };

  const handleFileChange = (event) => {
    const selectedFile = event.target.files?.[0] || null;
    selectFile(selectedFile);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);

    const droppedFile = event.dataTransfer.files?.[0] || null;
    selectFile(droppedFile);
  };

  const handleTemplateChange = (event) => {
    setTemplateId(event.target.value);
    resetResults();
  };

  const handleAnalyze = async () => {
    if (!file) {
      setError("Please upload a Word document before continuing.");
      return;
    }

    setLoadingAction("analyze");
    setError("");
    setAnalyzeResult(null);
    setFixResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("template_id", templateId);

      const response = await fetch(`${API_BASE}/documents/analyze`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data?.detail
            ? typeof data.detail === "string"
              ? data.detail
              : JSON.stringify(data.detail)
            : `Analysis failed with status ${response.status}.`
        );
      }

      setAnalyzeResult(data);
    } catch (requestError) {
      setError(
        requestError.message ||
          "We could not analyze this document. Please try again."
      );
    } finally {
      setLoadingAction("");
    }
  };

  const handleFix = async () => {
    if (!file) {
      setError("Please upload a Word document before continuing.");
      return;
    }

    setLoadingAction("fix");
    setError("");
    setFixResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("template_id", templateId);

      const response = await fetch(`${API_BASE}/documents/fix`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(
          data?.detail
            ? typeof data.detail === "string"
              ? data.detail
              : JSON.stringify(data.detail)
            : `Formatting failed with status ${response.status}.`
        );
      }

      setFixResult(data);
    } catch (requestError) {
      setError(
        requestError.message ||
          "We could not format this document. Please try again."
      );
    } finally {
      setLoadingAction("");
    }
  };

  const getDownloadUrl = () => {
    if (!fixResult?.download_url) {
      return null;
    }

    if (
      fixResult.download_url.startsWith("http://") ||
      fixResult.download_url.startsWith("https://")
    ) {
      return fixResult.download_url;
    }

    return `${API_BASE}${fixResult.download_url}`;
  };

  const downloadUrl = getDownloadUrl();

  const getStepState = (step) => {
    if (step === "upload") {
      return file ? "completed" : "active";
    }

    if (step === "analyze") {
      if (analyzeResult) return "completed";
      if (file) return "active";
      return "";
    }

    if (step === "fix") {
      if (fixResult) return "completed";
      if (analyzeResult) return "active";
      return "";
    }

    if (step === "download") {
      return fixResult ? "active" : "";
    }

    return "";
  };

  return (
    <main className="appShell">
      <header className="hero">
        <div className="brandBadge">APA 7</div>

        <h1>APA Document Formatter</h1>

        <p className="heroDescription">
          Check and correct APA 7 formatting in your Word document.
        </p>
      </header>

      <section className="stepper" aria-label="Document formatting progress">
        {[
          ["upload", "Upload"],
          ["analyze", "Analyze"],
          ["fix", "Fix"],
          ["download", "Download"],
        ].map(([key, label], index) => {
          const state = getStepState(key);

          return (
            <div
              className={`step ${state}`}
              key={key}
              aria-current={state === "active" ? "step" : undefined}
            >
              <div className="stepNumber">
                {state === "completed" ? "✓" : index + 1}
              </div>
              <span>{label}</span>
            </div>
          );
        })}
      </section>

      <section className="card uploadCard">
        <div className="cardHeader">
          <div>
            <p className="eyebrow">Step 1</p>
            <h2>Upload your document</h2>
          </div>

          {file && (
            <button
              type="button"
              className="textButton"
              onClick={resetWorkflow}
              disabled={isLoading}
            >
              Start over
            </button>
          )}
        </div>

        <input
          ref={fileInputRef}
          id="document-upload"
          className="hiddenFileInput"
          type="file"
          accept=".docx"
          onChange={handleFileChange}
        />

        {!file ? (
          <div
            className={`dropZone ${isDragging ? "dragging" : ""}`}
            onDragEnter={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                fileInputRef.current?.click();
              }
            }}
            role="button"
            tabIndex={0}
          >
            <div className="uploadIcon" aria-hidden="true">
              ↑
            </div>

            <h3>Drag and drop your .docx file</h3>
            <p>
              or <span>browse files</span> from your computer
            </p>

            <small>Microsoft Word .docx · Maximum size 10 MB</small>
          </div>
        ) : (
          <div className="selectedFile">
            <div className="fileIcon" aria-hidden="true">
              DOCX
            </div>

            <div className="selectedFileDetails">
              <strong>{file.name}</strong>
              <span>{formatFileSize(file.size)}</span>
            </div>

            <button
              type="button"
              className="removeFileButton"
              onClick={resetWorkflow}
              disabled={isLoading}
              aria-label="Remove selected file"
            >
              ×
            </button>
          </div>
        )}

        <div className="fieldGroup">
          <label htmlFor="template-select">Formatting template</label>

          <select
            id="template-select"
            value={templateId}
            onChange={handleTemplateChange}
            disabled={isLoading}
          >
            {TEMPLATE_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>

          <p className="fieldHint">
            More academic formatting templates can be added later.
          </p>
        </div>

        {error && (
          <div className="errorMessage" role="alert">
            <span aria-hidden="true">!</span>
            <p>{error}</p>
          </div>
        )}

        <div className="actionArea">
          {!analyzeResult && (
            <button
              type="button"
              className="primaryButton"
              onClick={handleAnalyze}
              disabled={!file || isLoading}
            >
              {loadingAction === "analyze" && (
                <span className="spinner" aria-hidden="true" />
              )}

              {loadingAction === "analyze"
                ? "Analyzing document..."
                : "Analyze Document"}
            </button>
          )}

          {analyzeResult && !fixResult && issueCount > 0 && (
            <>
              <button
                type="button"
                className="primaryButton"
                onClick={handleFix}
                disabled={isLoading}
              >
                {loadingAction === "fix" && (
                  <span className="spinner" aria-hidden="true" />
                )}

                {loadingAction === "fix"
                  ? "Applying corrections..."
                  : `Fix ${issueCount} Issues`}
              </button>

              <button
                type="button"
                className="secondaryButton"
                onClick={handleAnalyze}
                disabled={isLoading}
              >
                Analyze Again
              </button>
            </>
          )}

          {analyzeResult && !fixResult && issueCount === 0 && (
            <button
              type="button"
              className="secondaryButton"
              onClick={handleAnalyze}
              disabled={isLoading}
            >
              Analyze Again
            </button>
          )}
        </div>
      </section>

      {loadingAction === "analyze" && (
        <section className="card loadingCard" aria-live="polite">
          <span className="largeSpinner" aria-hidden="true" />

          <div>
            <h2>Analyzing your document</h2>
            <p>
              Checking margins, title page, typography, spacing and
              references.
            </p>
          </div>
        </section>
      )}

      {loadingAction === "fix" && (
        <section className="card loadingCard" aria-live="polite">
          <span className="largeSpinner" aria-hidden="true" />

          <div>
            <h2>Applying formatting corrections</h2>
            <p>
              This may take a few seconds. Please keep this page open.
            </p>
          </div>
        </section>
      )}

      {analyzeResult && (
        <section className="card resultCard">
          <div className="resultHeading">
            <div>
              <p className="eyebrow">Analysis complete</p>
              <h2>Formatting report</h2>
              <p className="resultFilename">{analyzeResult.filename}</p>
            </div>

            <span className="statusBadge">
              {analyzeResult.template === "apa7_student"
                ? "APA 7 Student Paper"
                : analyzeResult.template}
            </span>
          </div>

          <div className="scoreSection">
            <div className={`scoreCircle ${getScoreTone()}`}>
              <strong>{score}</strong>
              <span>/ 100</span>
            </div>

            <div className="scoreDetails">
              <p className="scoreLabel">Formatting score</p>
              <h3>{getScoreLabel()}</h3>

              <div
                className="scoreBar"
                role="progressbar"
                aria-label="Formatting score"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-valuenow={score}
              >
                <div
                  className={`scoreFill ${getScoreTone()}`}
                  style={{ width: `${score}%` }}
                />
              </div>

              <p>
                {issueCount === 0
                  ? "No formatting issues were detected."
                  : `${issueCount} formatting ${
                      issueCount === 1 ? "issue was" : "issues were"
                    } detected.`}
              </p>
            </div>
          </div>

          {Object.keys(groupedIssues).length > 0 ? (
            <div className="issuesSection">
              <div className="sectionHeading">
                <div>
                  <h3>Detected issues</h3>
                  <p>Expand a category to review its details.</p>
                </div>

                <span className="issueCountBadge">{issueCount}</span>
              </div>

              <div className="issueGroups">
                {Object.entries(groupedIssues).map(
                  ([category, issues], index) => (
                    <details
                      className="issueGroup"
                      key={category}
                      open={index === 0}
                    >
                      <summary>
                        <span>{category}</span>

                        <span className="categoryCount">
                          {issues.length}{" "}
                          {issues.length === 1 ? "issue" : "issues"}
                        </span>
                      </summary>

                      <ul>
                        {issues.map((issue, issueIndex) => (
                          <li key={`${category}-${issueIndex}`}>
                            <span className="issueBullet" aria-hidden="true">
                              !
                            </span>
                            <p>{issue.message}</p>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )
                )}
              </div>
            </div>
          ) : (
            <div className="successNotice">
              <span aria-hidden="true">✓</span>

              <div>
                <strong>Your document looks properly formatted.</strong>
                <p>
                  Review the document before submitting it to confirm that all
                  content is correct.
                </p>
              </div>
            </div>
          )}
        </section>
      )}

      {fixResult && (
        <section className="card completionCard">
          <div className="completionIcon" aria-hidden="true">
            ✓
          </div>

          <p className="eyebrow">Formatting complete</p>
          <h2>Your corrected document is ready</h2>

          <p className="completionDescription">
            {totalFixed > 0
              ? `${totalFixed} formatting changes were applied using the APA 7 Student Paper template.`
              : "No additional automatic formatting changes were required."}
          </p>

          {visibleFixedCounts.length > 0 && (
            <div className="fixedSummary">
              <h3>Changes applied</h3>

              <ul>
                {visibleFixedCounts.map((item) => (
                  <li key={item.key}>
                    <span className="checkIcon" aria-hidden="true">
                      ✓
                    </span>

                    <span>{item.label}</span>

                    <strong>{item.value}</strong>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="downloadArea">
            {downloadUrl && (
              <a
                className="downloadButton"
                href={downloadUrl}
                target="_blank"
                rel="noreferrer"
              >
                <span aria-hidden="true">↓</span>
                Download Fixed Document
              </a>
            )}

            <button
              type="button"
              className="secondaryButton"
              onClick={resetWorkflow}
            >
              Format Another Document
            </button>
          </div>

          <p className="reviewNotice">
            Review the corrected document in Microsoft Word before submitting
            it.
          </p>

          {fixResult.fixed_counts && (
            <details className="technicalDetails">
              <summary>View technical details</summary>

              <pre>
                {JSON.stringify(fixResult.fixed_counts, null, 2)}
              </pre>
            </details>
          )}
        </section>
      )}

      <footer className="footer">
        <p>DOC Formatter · APA 7 Student Paper</p>
      </footer>
    </main>
  );
}

export default App;
