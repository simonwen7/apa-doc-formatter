import IssueGroup from "./IssueGroup";
import { groupIssuesByCategory } from "../utils/normalizeAnalysisResponse";

export default function FormattingSuccess({
  fixModel,
  visibleFixedCounts,
  totalFixed,
  downloadUrl,
  onDownload,
  onAnalyzeAgain,
  onResetWorkflow,
}) {
  if (!fixModel) return null;

  const {
    formattingSucceeded,
    remainingAuthorIssues,
    remainingAuthorCount,
    remainingUncertainIssues,
    verification,
  } = fixModel;

  if (!formattingSucceeded) {
    return (
      <div className="previewScroll">
        <article className="documentPage">
          <div className="errorPanel" role="alert">
            <span aria-hidden="true">!</span>
            <div>
              <strong>We couldn&apos;t safely finish formatting this document.</strong>
              <p>
                Your original document has not been changed. Please try again or
                review the document manually.
              </p>
            </div>
          </div>

          <div className="downloadArea" style={{ marginTop: 24 }}>
            <button
              type="button"
              className="secondaryButton"
              onClick={onAnalyzeAgain}
            >
              Analyze Again
            </button>
            <button
              type="button"
              className="secondaryButton"
              onClick={onResetWorkflow}
            >
              Start over
            </button>
          </div>
        </article>
      </div>
    );
  }

  const authorGroups = Object.entries(
    groupIssuesByCategory(remainingAuthorIssues)
  );
  const uncertainGroups = Object.entries(
    groupIssuesByCategory(remainingUncertainIssues)
  );
  const fixedSafe = verification.safeIssuesBefore;

  return (
    <div className="previewScroll">
      <article className="documentPage">
        <div className="successIndicator">
          <span className="successDot" aria-hidden="true" />
          Formatting complete
        </div>

        <h3>Your paper is formatted.</h3>

        <p className="completionDescription">
          {fixedSafe > 0
            ? `All ${fixedSafe} supported formatting ${
                fixedSafe === 1 ? "issue was" : "issues were"
              } corrected without changing your written content.`
            : totalFixed > 0
              ? `${totalFixed} formatting changes were applied without changing your written content.`
              : "Supported formatting checks passed without changing your written content."}
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

        {remainingAuthorCount > 0 && (
          <section
            className="reportSection postFixReview"
            aria-labelledby="post-fix-review-heading"
          >
            <div className="sectionHeading">
              <div>
                <h4 id="post-fix-review-heading">Needs your review</h4>
                <p>
                  {remainingAuthorCount} APA{" "}
                  {remainingAuthorCount === 1 ? "item still requires" : "items still require"}{" "}
                  your attention. Forma APA does not rewrite citations, references,
                  or other written content.
                </p>
              </div>
              <span className="issueCountBadge issueCountBadge--review">
                {remainingAuthorCount}
              </span>
            </div>

            <div className="issueGroups">
              {authorGroups.map(([category, issues], index) => (
                <IssueGroup
                  key={`post-review-${category}`}
                  category={category}
                  issues={issues}
                  variant="review"
                  defaultOpen={index === 0}
                />
              ))}
            </div>
          </section>
        )}

        {uncertainGroups.length > 0 && (
          <section className="reportSection" aria-labelledby="post-uncertain-heading">
            <div className="sectionHeading">
              <div>
                <h4 id="post-uncertain-heading">May need review</h4>
                <p>Possible issues that are not definite failures.</p>
              </div>
            </div>
            <div className="issueGroups">
              {uncertainGroups.map(([category, issues]) => (
                <IssueGroup
                  key={`post-uncertain-${category}`}
                  category={category}
                  issues={issues}
                  variant="uncertain"
                />
              ))}
            </div>
          </section>
        )}

        <div className="downloadArea">
          {downloadUrl && (
            <button
              type="button"
              className="downloadButton"
              onClick={onDownload}
            >
              <span aria-hidden="true">↓</span>
              Download formatted document
            </button>
          )}

          <button
            type="button"
            className="secondaryButton"
            onClick={onAnalyzeAgain}
          >
            Analyze Again
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
          Review the corrected document in Microsoft Word before submitting it.
          Formatting success does not mean the paper is fully APA-correct.
        </p>
      </article>
    </div>
  );
}
