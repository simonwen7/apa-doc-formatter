export default function HeroSection({ onFormatClick }) {
  return (
    <section className="heroSection" aria-labelledby="hero-heading">
      <p className="heroEyebrow animate-fade-rise">
        APA 7 • Academic document formatting
      </p>

      <h1 id="hero-heading" className="heroHeading animate-fade-rise-delay">
        Turn your <span className="ideas">ideas</span> into a paper{" "}
        <span className="mutedWord">ready to submit.</span>
      </h1>

      <p className="heroDescription animate-fade-rise-delay-2">
        Format your document with consistent APA 7 structure, spacing,
        typography, headings, and references—without rebuilding every page by
        hand.
      </p>

      <div className="heroActions animate-fade-rise-delay-2">
        <button
          type="button"
          className="primaryButton"
          onClick={onFormatClick}
        >
          Format a Document
        </button>

        <a className="secondaryButton" href="#how-it-works">
          See How It Works
        </a>
      </div>
    </section>
  );
}
