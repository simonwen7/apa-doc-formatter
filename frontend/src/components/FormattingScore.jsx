export default function FormattingScore({
  score,
  scoreLabel,
  scoreTone,
  safeCount,
  authorCount,
}) {
  return (
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
          Based on formatting issues Forma APA can safely detect and fix.
        </p>

        <div className="scoreSplitStats" aria-label="Issue summary">
          <div>
            <strong>{safeCount}</strong>
            <span>
              {safeCount === 1
                ? "formatting issue Forma APA can fix"
                : "formatting issues Forma APA can fix"}
            </span>
          </div>
          <div>
            <strong>{authorCount}</strong>
            <span>
              {authorCount === 1
                ? "item needs your review"
                : "items need your review"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
