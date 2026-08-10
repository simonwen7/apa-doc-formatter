export default function HeroSection({ onFormatClick }) {
  return (
    <section className="heroSection" aria-labelledby="hero-heading">
      <p className="heroEyebrow animate-fade-rise">
        APA 7 • Academic document formatting
      </p>

      <h1 id="hero-heading" className="heroHeading animate-fade-rise-delay">
        Turn your <span className="ideas">ideas</span> into a paper with{" "}
        <span className="mutedWord">cleaner APA formatting.</span>
      </h1>

      <p className="heroDescription animate-fade-rise-delay-2">
        Forma APA checks supported APA 7 Student Paper formatting, safely fixes
        formatting-only issues, and flags items that still need your review—without
        rewriting your words.
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
