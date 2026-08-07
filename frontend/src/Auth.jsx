import { useState } from "react";
import penIcon from "./assets/pen-icon.png";
import { VIDEO_SRC, usePrefersReducedMotion } from "./hooks/useAtmosphere";
import { supabase } from "./supabaseClient";

function Auth() {
  const prefersReducedMotion = usePrefersReducedMotion();
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const isRegistering = mode === "register";

  const clearFeedback = () => {
    setError("");
    setMessage("");
  };

  const changeMode = (nextMode) => {
    setMode(nextMode);
    setPassword("");
    setConfirmPassword("");
    clearFeedback();
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    clearFeedback();

    const normalizedEmail = email.trim().toLowerCase();

    if (!normalizedEmail) {
      setError("Please enter your email address.");
      return;
    }

    if (password.length < 8) {
      setError("Your password must contain at least 8 characters.");
      return;
    }

    if (isRegistering && password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      if (isRegistering) {
        const { data, error: signUpError } = await supabase.auth.signUp({
          email: normalizedEmail,
          password,
          options: {
            emailRedirectTo: window.location.origin,
          },
        });

        if (signUpError) {
          throw signUpError;
        }

        if (!data.session) {
          setMessage(
            "Account created. Please check your email before signing in."
          );
        }
      } else {
        const { error: signInError } = await supabase.auth.signInWithPassword({
          email: normalizedEmail,
          password,
        });

        if (signInError) {
          throw signInError;
        }
      }
    } catch (requestError) {
      setError(
        requestError?.message || "Authentication failed. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="authPage">
      <section className="authBrandPanel" aria-hidden={false}>
        {prefersReducedMotion ? (
          <div className="authBrandStatic" aria-hidden="true" />
        ) : (
          <video
            className="authBrandVideo"
            src={VIDEO_SRC}
            autoPlay
            loop
            muted
            playsInline
            aria-hidden="true"
          />
        )}
        <div className="authBrandOverlay" aria-hidden="true" />

        <div className="authBrandContent">
          <span className="authLogo">
            <img src={penIcon} alt="" className="brandLogoIcon" aria-hidden="true" />
            <span>
              Forma APA
              <mark>®</mark>
            </span>
          </span>

          <h1>Better formatting. More time for your ideas.</h1>

          <p>
            Analyze and correct your APA 7 Word document before submitting it.
          </p>

          <ul className="authBenefits">
            <li>
              <span>✓</span>
              Detect formatting problems
            </li>
            <li>
              <span>✓</span>
              Apply automatic corrections
            </li>
            <li>
              <span>✓</span>
              Download the corrected document
            </li>
          </ul>
        </div>
      </section>

      <section className="authFormPanel" id="auth-form">
        <div className="authCard">
          <div className="authHeading">
            <span className="mobileAuthLogo authLogo">
              <img src={penIcon} alt="" className="brandLogoIcon" aria-hidden="true" />
              <span>
                Forma APA
                <mark>®</mark>
              </span>
            </span>

            <h2>{isRegistering ? "Create your account" : "Welcome back"}</h2>

            <p>
              {isRegistering
                ? "Create an account to format your documents."
                : "Sign in to continue to Forma APA."}
            </p>
          </div>

          <div className="authTabs">
            <button
              type="button"
              className={mode === "login" ? "active" : ""}
              onClick={() => changeMode("login")}
              disabled={loading}
            >
              Sign in
            </button>

            <button
              type="button"
              className={mode === "register" ? "active" : ""}
              onClick={() => changeMode("register")}
              disabled={loading}
            >
              Create account
            </button>
          </div>

          <form className="authForm" onSubmit={handleSubmit}>
            <div className="authField">
              <label htmlFor="auth-email">Email address</label>

              <input
                id="auth-email"
                type="email"
                autoComplete="email"
                placeholder="name@example.com"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  clearFeedback();
                }}
                disabled={loading}
                required
              />
            </div>

            <div className="authField">
              <label htmlFor="auth-password">Password</label>

              <div className="passwordInputWrapper">
                <input
                  id="auth-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete={
                    isRegistering ? "new-password" : "current-password"
                  }
                  placeholder="Enter your password"
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value);
                    clearFeedback();
                  }}
                  disabled={loading}
                  required
                />

                <button
                  type="button"
                  className="showPasswordButton"
                  onClick={() => setShowPassword((current) => !current)}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>

              {isRegistering && <small>Use at least 8 characters.</small>}
            </div>

            {isRegistering && (
              <div className="authField">
                <label htmlFor="confirm-password">Confirm password</label>

                <input
                  id="confirm-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="Enter your password again"
                  value={confirmPassword}
                  onChange={(event) => {
                    setConfirmPassword(event.target.value);
                    clearFeedback();
                  }}
                  disabled={loading}
                  required
                />
              </div>
            )}

            {error && (
              <div className="authError" role="alert">
                <span>!</span>
                <p>{error}</p>
              </div>
            )}

            {message && (
              <div className="authSuccess" role="status">
                <span>✓</span>
                <p>{message}</p>
              </div>
            )}

            <button
              type="submit"
              className="authSubmitButton"
              disabled={loading}
            >
              {loading
                ? "Please wait..."
                : isRegistering
                  ? "Create Account"
                  : "Sign In"}
            </button>
          </form>

          <p className="authSwitchText">
            {isRegistering
              ? "Already have an account?"
              : "New to Forma APA?"}

            <button
              type="button"
              onClick={() =>
                changeMode(isRegistering ? "login" : "register")
              }
              disabled={loading}
            >
              {isRegistering ? "Sign in" : "Create an account"}
            </button>
          </p>
        </div>
      </section>
    </main>
  );
}

export default Auth;
