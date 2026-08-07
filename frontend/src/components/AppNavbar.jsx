import { useState } from "react";

const NAV_ITEMS = [
  { id: "formatter", label: "Formatter", href: "#workspace" },
  { id: "how-it-works", label: "How It Works", href: "#how-it-works" },
  { id: "apa-guide", label: "APA Guide", href: "#workspace" },
  { id: "my-documents", label: "My Documents", href: "#workspace" },
];

function getInitial(email = "") {
  const value = email.trim();
  return value ? value.charAt(0).toUpperCase() : "U";
}

export default function AppNavbar({
  session,
  onSignOut,
  activeSection = "formatter",
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const email = session?.user?.email || "";

  const closeMenu = () => setMenuOpen(false);

  return (
    <nav className="appNavbar" aria-label="Primary">
      <div className="appNavbarInner">
        <a className="brandLogo" href="#top" onClick={closeMenu}>
          Forma APA
          <mark>®</mark>
        </a>

        <div className="navLinks">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.id}
              href={item.href}
              className={activeSection === item.id ? "isActive" : ""}
            >
              {item.label}
            </a>
          ))}
        </div>

        <div className="navActions">
          {session ? (
            <>
              <div className="accountChip">
                <span className="accountEmail" title={email}>
                  {email}
                </span>
                <span className="accountAvatar" aria-hidden="true">
                  {getInitial(email)}
                </span>
              </div>

              <button
                type="button"
                className="ghostButton"
                onClick={onSignOut}
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <a className="ghostButton" href="#auth-form">
                Sign In
              </a>
              <a className="glassButton liquid-glass" href="#auth-form">
                Get Started
              </a>
            </>
          )}

          <button
            type="button"
            className="menuToggle"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span className="menuToggleBars" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          </button>
        </div>
      </div>

      {menuOpen && (
        <div className="mobileNav liquid-glass-panel">
          {NAV_ITEMS.map((item) => (
            <a
              key={item.id}
              href={item.href}
              className={activeSection === item.id ? "isActive" : ""}
              onClick={closeMenu}
            >
              {item.label}
            </a>
          ))}

          {session && (
            <button
              type="button"
              onClick={() => {
                closeMenu();
                onSignOut();
              }}
            >
              Sign out
            </button>
          )}
        </div>
      )}
    </nav>
  );
}
