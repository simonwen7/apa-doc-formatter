export default function HowItWorks() {
  const steps = [
    {
      number: "01",
      title: "Add your document",
      description:
        "Upload a Word document and choose the APA 7 Student Paper template.",
    },
    {
      number: "02",
      title: "Confirm paper details",
      description:
        "Review the formatting style, then analyze spacing, typography, and structure.",
    },
    {
      number: "03",
      title: "Preview and download",
      description:
        "Apply supported formatting fixes, review author items, and download your file.",
    },
  ];

  return (
    <section
      id="how-it-works"
      className="howItWorks"
      aria-labelledby="how-it-works-heading"
    >
      <h2 id="how-it-works-heading" className="howItWorksHeading">
        From draft to formatted paper.
      </h2>

      <div className="howItWorksGrid">
        {steps.map((step) => (
          <article className="howStep" key={step.number}>
            <span className="howStepNumber">{step.number}</span>
            <h3>{step.title}</h3>
            <p>{step.description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
