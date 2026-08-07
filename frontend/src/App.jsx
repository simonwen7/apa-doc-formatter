import { useEffect, useState } from "react";
import Auth from "./Auth";
import AtmosphereBackground from "./components/AtmosphereBackground";
import AppNavbar from "./components/AppNavbar";
import FormatterApp from "./FormatterApp";
import { supabase } from "./supabaseClient";

function App() {
  const [session, setSession] = useState(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const [signOutError, setSignOutError] = useState("");

  useEffect(() => {
    let isMounted = true;

    const loadSession = async () => {
      const {
        data: { session: currentSession },
        error,
      } = await supabase.auth.getSession();

      if (!isMounted) {
        return;
      }

      if (error) {
        console.error("Unable to load session:", error);
      }

      setSession(currentSession);
      setCheckingSession(false);
    };

    loadSession();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setCheckingSession(false);
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const handleSignOut = async () => {
    setSignOutError("");

    const { error } = await supabase.auth.signOut();

    if (error) {
      setSignOutError(error.message);
    }
  };

  if (checkingSession) {
    return (
      <main className="sessionLoadingPage">
        <span className="largeSpinner" aria-hidden="true" />
        <p>Loading your account...</p>
      </main>
    );
  }

  if (!session) {
    return <Auth />;
  }

  return (
    <div id="top" className="appRoot">
      <AtmosphereBackground />

      <div className="appContent">
        <AppNavbar session={session} onSignOut={handleSignOut} />

        {signOutError && (
          <p className="headerError" role="alert">
            {signOutError}
          </p>
        )}

        <FormatterApp />
      </div>
    </div>
  );
}

export default App;
