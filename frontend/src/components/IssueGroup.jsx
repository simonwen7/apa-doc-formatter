export default function IssueGroup({
  category,
  issues,
  variant = "safe",
  defaultOpen = false,
}) {
  const countLabel =
    issues.length === 1
      ? variant === "safe"
        ? "1 formatting issue"
        : "1 item"
      : variant === "safe"
        ? `${issues.length} formatting issues`
        : `${issues.length} items`;

  return (
    <details className={`issueGroup issueGroup--${variant}`} open={defaultOpen}>
      <summary>
        <span>{category}</span>
        <span className="categoryCount">{countLabel}</span>
      </summary>

      <ul>
        {issues.map((issue, index) => (
          <li key={`${issue.ruleId || category}-${index}`}>
            <span
              className={`issueBullet issueBullet--${variant}`}
              aria-hidden="true"
            >
              {variant === "review" ? "R" : variant === "uncertain" ? "?" : "!"}
            </span>
            <div className="issueBody">
              <p>{issue.message}</p>

              {(issue.expected || issue.actual || issue.location) && (
                <dl className="issueMeta">
                  {issue.expected ? (
                    <>
                      <dt>Expected</dt>
                      <dd>{issue.expected}</dd>
                    </>
                  ) : null}
                  {issue.actual ? (
                    <>
                      <dt>Found</dt>
                      <dd>{issue.actual}</dd>
                    </>
                  ) : null}
                  {issue.location ? (
                    <>
                      <dt>Location</dt>
                      <dd>{issue.location}</dd>
                    </>
                  ) : null}
                </dl>
              )}

              {variant !== "safe" && issue.reasonNotFixable ? (
                <p className="issueReason">
                  <span className="reviewPill">Why Forma APA won&apos;t change this</span>
                  {issue.reasonNotFixable}
                </p>
              ) : null}

              {variant === "uncertain" ? (
                <span className="possibleIssuePill">Possible issue</span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </details>
  );
}
