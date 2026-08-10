import FormattingReport from "./FormattingReport";
import FormattingSuccess from "./FormattingSuccess";

export default function DocumentInputPanel({
  activeTab,
  onTabChange,
  fileInputRef,
  file,
  isDragging,
  isLoading,
  error,
  loadingAction,
  analyzeResult,
  analysis,
  fixResult,
  fixModel,
  scoreLabel,
  scoreTone,
  visibleFixedCounts,
  totalFixed,
  downloadUrl,
  onDownload,
  formatFileSize,
  onFileChange,
  onDrop,
  onDragEnter,
  onDragOver,
  onDragLeave,
  onBrowse,
  onResetWorkflow,
  onFix,
  onAnalyzeAgain,
}) {
  const showUpload = activeTab === "upload";
  const showPreview = activeTab === "preview";

  return (
    <section
      className="panel liquid-glass-panel documentPanel"
      aria-labelledby="document-panel-heading"
    >
      <h3 id="document-panel-heading" className="sr-only">
        Document input and results
      </h3>

      <div className="segmentedControl" role="tablist" aria-label="Document views">
        <button
          type="button"
          role="tab"
          aria-selected={showUpload}
          className={showUpload ? "isActive" : ""}
          onClick={() => onTabChange("upload")}
        >
          Upload
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={showPreview}
          className={showPreview ? "isActive" : ""}
          onClick={() => onTabChange("preview")}
          disabled={!analyzeResult && !fixResult && !loadingAction}
        >
          Preview
        </button>
      </div>

      {showUpload && (
        <div role="tabpanel">
          <input
            ref={fileInputRef}
            id="document-upload"
            className="hiddenFileInput"
            type="file"
            accept=".docx"
            onChange={onFileChange}
          />

          {!file ? (
            <div
              className={`dropZone liquid-glass ${isDragging ? "dragging" : ""}`}
              onDragEnter={onDragEnter}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              onClick={onBrowse}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onBrowse();
                }
              }}
              role="button"
              tabIndex={0}
              aria-label="Upload a Word document"
            >
              <div className="dropZoneIcon" aria-hidden="true">
                ▤
              </div>
              <h3>Drop your paper here</h3>
              <p>
                Upload your document or <span>browse your files</span>.
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
                onClick={onResetWorkflow}
                disabled={isLoading}
                aria-label="Remove selected file"
              >
                ×
              </button>
            </div>
          )}

          {error && (
            <div className="errorPanel" role="alert">
              <span aria-hidden="true">!</span>
              <div>
                <strong>Something went wrong</strong>
                <p>{error}</p>
              </div>
            </div>
          )}

          {loadingAction === "analyze" && (
            <div className="statusCard" aria-live="polite">
              <span className="largeSpinner" aria-hidden="true" />
              <div>
                <h3>Preparing your APA document…</h3>
                <p>
                  Checking margins, title page, typography, spacing, and
                  references.
                </p>
              </div>
            </div>
          )}

          {loadingAction === "fix" && (
            <div className="statusCard" aria-live="polite">
              <span className="largeSpinner" aria-hidden="true" />
              <div>
                <h3>Applying APA formatting…</h3>
                <p>
                  Correcting supported formatting only. Your written content is
                  not rewritten.
                </p>
              </div>
            </div>
          )}

          {!file && !error && !loadingAction && (
            <div className="emptyPreview" style={{ minHeight: 200, marginTop: 24 }}>
              <p style={{ margin: 0, color: "hsl(var(--subtle-foreground))" }}>
                Supported input: Word documents (.docx) only.
              </p>
            </div>
          )}
        </div>
      )}

      {showPreview && (
        <div role="tabpanel" className="resultStack">
          {!analyzeResult && !fixResult && !loadingAction && (
            <div className="emptyPreview">
              <div className="emptyPreviewIcon" aria-hidden="true">
                ⌕
              </div>
              <h3>Your formatted paper will appear here.</h3>
              <p>
                Add your document and complete the paper setup to generate an
                APA formatting report.
              </p>
            </div>
          )}

          {loadingAction && !fixResult && (
            <div className="statusCard" aria-live="polite">
              <span className="largeSpinner" aria-hidden="true" />
              <div>
                <h3>
                  {loadingAction === "fix"
                    ? "Applying APA formatting…"
                    : "Preparing your APA document…"}
                </h3>
                <p>
                  {loadingAction === "fix"
                    ? "Formatting your document without changing your written content."
                    : "Results will appear here when analysis is complete."}
                </p>
              </div>
            </div>
          )}

          {analyzeResult && analysis && !fixResult && !loadingAction && (
            <FormattingReport
              analysis={analysis}
              scoreLabel={scoreLabel}
              scoreTone={scoreTone}
              isLoading={isLoading}
              loadingAction={loadingAction}
              onFix={onFix}
              onAnalyzeAgain={onAnalyzeAgain}
            />
          )}

          {fixResult && fixModel && (
            <FormattingSuccess
              fixModel={fixModel}
              visibleFixedCounts={visibleFixedCounts}
              totalFixed={totalFixed}
              downloadUrl={downloadUrl}
              onDownload={onDownload}
              onAnalyzeAgain={onAnalyzeAgain}
              onResetWorkflow={onResetWorkflow}
            />
          )}
        </div>
      )}
    </section>
  );
}
