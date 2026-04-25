import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { AuthProvider } from "./contexts/AuthContext";
import { InterviewProvider } from "./contexts/InterviewContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AuthProvider>
      <InterviewProvider>
        <App />
      </InterviewProvider>
    </AuthProvider>
  </React.StrictMode>
);
