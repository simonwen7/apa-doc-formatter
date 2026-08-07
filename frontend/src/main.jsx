import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/theme.css";
import "./styles/glass.css";
import "./styles/animations.css";
import "./styles/layout.css";
import "./styles/formatter.css";
import "./styles/auth.css";
import App from "./App.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
