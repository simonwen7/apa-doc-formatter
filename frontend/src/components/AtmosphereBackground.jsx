import { VIDEO_SRC, usePrefersReducedMotion } from "../hooks/useAtmosphere";

export default function AtmosphereBackground() {
  const prefersReducedMotion = usePrefersReducedMotion();

  return (
    <div className="atmosphere" aria-hidden="true">
      {prefersReducedMotion ? (
        <div className="atmosphereStatic" />
      ) : (
        <video
          className="atmosphereVideo"
          src={VIDEO_SRC}
          autoPlay
          loop
          muted
          playsInline
        />
      )}
      <div className="atmosphereOverlay" />
    </div>
  );
}
