import FormattingScore from "./FormattingScore";
import IssueGroup from "./IssueGroup";
import { formattingFixButtonLabel } from "../utils/normalizeAnalysisResponse";

export default function FormattingReport({
  analysis,
  scoreLabel,
  scoreTone,
  isLoading,
  loadingAction,
  onFix,
  onAnalyzeAgain,
}) {
  if (!analysis) return null;

  const {
    filename,
    template,
    formattingScore,
    safeCount,
    authorCount,
    uncertainCount,
    canFix,
    groupedSafeIssues,
    groupedAuthorIssues,
    groupedUncertainIssues,
  } = analysis;

  const safeEntries = Object.entries(groupedSafeIssues);
  const authorEntries = Object.entries(groupedAuthorIssues);
  const uncertainEntries = Object.entries(groupedUncertainIssues);
  const fixLabel = formattingFixButtonLabel(safeCount);

  return (
    <div className="resultStack">
      <div className="resultHeadingRow">
        <div>
          <p className="eyebrow">Analysis complete</p>
          <h3>Formatting report</h3>
          <p className="resultFilename">{filename}</p>
        </div>

        <span className="templateBadge">
          {template === "apa7_student" ? "APA 7 Student Paper" : template}
        </span>
      </div>

      <FormattingScore
        score={formattingScore}
        scoreLabel={scoreLabel}
        scoreTone={scoreTone}
        safeCount={safeCount}
        authorCount={authorCount}
      />

      {safeCount === 0 ? (
        <div className="successNotice" role="status">
          <span aria-hidden="true">✓</span>
          <div>
            <strong>Formatting checks passed</strong>
            <p>
              {authorCount > 0
                ? "All supported formatting checks passed. Some APA items still need your review below."
                : "No supported formatting issues were detected. This does not guarantee complete APA correctness."}
            </p>
          </div>
        </div>
      ) : (
        <section className="reportSection" aria-labelledby="safe-issues-heading">
          <div className="sectionHeading">
            <div>
              <h4 id="safe-issues-heading">
                Formatting issues Forma APA can fix
              </h4>
              <p>These are formatting corrections only — your wording stays unchanged.</p>
            </div>
            <span className="issueCountBadge">{safeCount}</span>
          </div>

          <div className="issueGroups">
            {safeEntries.map(([category, issues], index) => (
              <IssueGroup
                key={`safe-${category}`}
                category={category}
                issues={issues}
                variant="safe"
                defaultOpen={index === 0}
              />
            ))}
          </div>
        </section>
      )}

      {authorCount > 0 && (
        <section className="reportSection" aria-labelledby="review-issues-heading">
          <div className="sectionHeading">
            <div>
              <h4 id="review-issues-heading">Needs your review</h4>
              <p>
                These APA issues may require changes to wording, citations,
                references, or missing information. Forma APA will never change
                your written content automatically.
              </p>
            </div>
            <span className="issueCountBadge issueCountBadge--review">
              {authorCount}
            </span>
          </div>

          <div className="issueGroups">
            {authorEntries.map(([category, issues], index) => (
              <IssueGroup
                key={`review-${category}`}
                category={category}
                issues={issues}
                variant="review"
                defaultOpen={safeCount === 0 && index === 0}
              />
            ))}
          </div>
        </section>
      )}

      {uncertainCount > 0 && (
        <section className="reportSection" aria-labelledby="uncertain-issues-heading">
          <div className="sectionHeading">
            <div>
              <h4 id="uncertain-issues-heading">May need review</h4>
              <p>
                These items are possible issues. They are not definite failures.
              </p>
            </div>
            <span className="issueCountBadge issueCountBadge--uncertain">
              {uncertainCount}
            </span>
          </div>

          <div className="issueGroups">
            {uncertainEntries.map(([category, issues]) => (
              <IssueGroup
                key={`uncertain-${category}`}
                category={category}
                issues={issues}
                variant="uncertain"
              />
            ))}
          </div>
        </section>
      )}

      <div className="actionStack">
        {canFix && (
          <button
            type="button"
            className="primaryButton isFull"
            onClick={onFix}
            disabled={isLoading}
            aria-busy={loadingAction === "fix"}
          >
            {loadingAction === "fix" && (
              <span className="spinner" aria-hidden="true" />
            )}
            {loadingAction === "fix" ? "Applying APA formatting…" : fixLabel}
          </button>
        )}

        <button
          type="button"
          className="secondaryButton"
          onClick={onAnalyzeAgain}
          disabled={isLoading}
        >
          Analyze Again
        </button>
      </div>
    </div>
  );
}
