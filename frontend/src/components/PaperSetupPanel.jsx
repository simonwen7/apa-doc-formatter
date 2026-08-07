export default function PaperSetupPanel({
  templateId,
  templateOptions,
  onTemplateChange,
  isLoading,
  onAnalyze,
  onFix,
  onAnalyzeAgain,
  file,
  analyzeResult,
  fixResult,
  issueCount,
  loadingAction,
}) {
  const selectedTemplate =
    templateOptions.find((option) => option.id === templateId) ||
    templateOptions[0];

  return (
    <aside className="panel liquid-glass-panel" aria-labelledby="paper-setup-heading">
      <h3 id="paper-setup-heading" className="panelHeading">
        Paper setup
      </h3>
      <p className="panelSubheading">
        Choose how the paper should be structured before formatting.
      </p>

      <div className="fieldGroup">
        <label htmlFor="template-select">Formatting style</label>

        <select
          id="template-select"
          value={templateId}
          onChange={onTemplateChange}
          disabled={isLoading}
        >
          {templateOptions.map((option) => (
            <option key={option.id} value={option.id}>
              {option.label}
            </option>
          ))}
        </select>

        <div className="templateCard" aria-live="polite">
          <strong>{selectedTemplate?.label}</strong>
          <span>
            Designed for student papers using APA Seventh Edition guidelines.
          </span>
        </div>
      </div>

      <div className="actionStack">
        {!analyzeResult && (
          <button
            type="button"
            className="primaryButton isFull"
            onClick={onAnalyze}
            disabled={!file || isLoading}
          >
            {loadingAction === "analyze" && (
              <span className="spinner" aria-hidden="true" />
            )}
            {loadingAction === "analyze"
              ? "Analyzing…"
              : "Format Document"}
          </button>
        )}

        {analyzeResult && !fixResult && issueCount > 0 && (
          <>
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

            <button
              type="button"
              className="secondaryButton"
              onClick={onAnalyzeAgain}
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
            onClick={onAnalyzeAgain}
            disabled={isLoading}
          >
            Analyze Again
          </button>
        )}

        {fixResult && (
          <button
            type="button"
            className="secondaryButton"
            onClick={onAnalyzeAgain}
            disabled={isLoading}
          >
            Adjust Formatting
          </button>
        )}
      </div>
    </aside>
  );
}
