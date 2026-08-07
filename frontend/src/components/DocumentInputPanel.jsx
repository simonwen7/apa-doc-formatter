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
  fixResult,
  issueCount,
  score,
  scoreLabel,
  scoreTone,
  groupedIssues,
  visibleFixedCounts,
  totalFixed,
  downloadUrl,
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
                <h3>Formatting…</h3>
                <p>
                  Applying APA corrections. Please keep this page open.
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
                APA-ready preview.
              </p>
            </div>
          )}

          {loadingAction && (
            <div className="statusCard" aria-live="polite">
              <span className="largeSpinner" aria-hidden="true" />
              <div>
                <h3>Preparing your APA document…</h3>
                <p>Results will appear here when formatting is complete.</p>
              </div>
            </div>
          )}

          {analyzeResult && !fixResult && (
            <div className="resultStack">
              <div className="resultHeadingRow">
                <div>
                  <p className="eyebrow">Analysis complete</p>
                  <h3>Formatting report</h3>
                  <p className="resultFilename">{analyzeResult.filename}</p>
                </div>

                <span className="templateBadge">
                  {analyzeResult.template === "apa7_student"
                    ? "APA 7 Student Paper"
                    : analyzeResult.template}
                </span>
              </div>

              <div className="scoreSection">
                <div className={`scoreCircle ${scoreTone}`}>
                  <strong>{score}</strong>
                  <span>/ 100</span>
                </div>

                <div className="scoreDetails">
                  <p className="scoreLabel">Formatting score</p>
                  <h4>{scoreLabel}</h4>

                  <div
                    className="scoreBar"
                    role="progressbar"
                    aria-label="Formatting score"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={score}
                  >
                    <div
                      className={`scoreFill ${scoreTone}`}
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
                <div>
                  <div className="sectionHeading">
                    <div>
                      <h4>Detected issues</h4>
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
                      Review the document before submitting it to confirm that
                      all content is correct.
                    </p>
                  </div>
                </div>
              )}

              {issueCount > 0 && (
                <div className="actionStack">
                  <button
                    type="button"
                    className="primaryButton isFull"
                    onClick={onFix}
                    disabled={isLoading}
                  >
                    {loadingAction === "fix" && (
                      <span className="spinner" aria-hidden="true" />
                    )}
                    {loadingAction === "fix"
                      ? "Formatting…"
                      : `Fix ${issueCount} Issues`}
                  </button>
                </div>
              )}
            </div>
          )}

          {fixResult && (
            <div className="previewScroll">
              <article className="documentPage">
                <div className="successIndicator">
                  <span className="successDot" aria-hidden="true" />
                  Formatting complete
                </div>

                <h3>Your paper is ready.</h3>

                <p className="completionDescription">
                  {totalFixed > 0
                    ? `${totalFixed} formatting changes were applied using the APA 7 Student Paper template.`
                    : "No additional automatic formatting changes were required."}
                </p>

                {visibleFixedCounts.length > 0 && (
                  <div className="fixedSummary">
                    <h4>Changes applied</h4>
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
                      Download Formatted Document
                    </a>
                  )}

                  <button
                    type="button"
                    className="secondaryButton"
                    onClick={onAnalyzeAgain}
                  >
                    Adjust Formatting
                  </button>

                  <button
                    type="button"
                    className="secondaryButton"
                    onClick={onResetWorkflow}
                  >
                    Start over
                  </button>
                </div>

                <p className="reviewNotice">
                  Review the corrected document in Microsoft Word before
                  submitting it.
                </p>

                {fixResult.fixed_counts && (
                  <details className="technicalDetails">
                    <summary>View technical details</summary>
                    <pre>
                      {JSON.stringify(fixResult.fixed_counts, null, 2)}
                    </pre>
                  </details>
                )}
              </article>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
