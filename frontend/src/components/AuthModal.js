import React, { useState } from "react";
import { X } from "lucide-react";
import { useAuth } from "../context/AuthContext";

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#FFC107" d="M43.611 20.083H42V20H24v8h11.303C33.655 32.657 29.196 36 24 36c-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.959 3.041l5.657-5.657C34.053 6.053 29.277 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z" />
      <path fill="#FF3D00" d="M6.306 14.691l6.571 4.819C14.655 16.108 19.001 12 24 12c3.059 0 5.842 1.154 7.959 3.041l5.657-5.657C34.053 6.053 29.277 4 24 4c-7.681 0-14.41 4.337-17.694 10.691z" />
      <path fill="#4CAF50" d="M24 44c5.176 0 9.86-1.977 13.409-5.192l-6.19-5.238C29.144 35.091 26.692 36 24 36c-5.176 0-9.626-3.328-11.29-7.946l-6.522 5.025C9.438 39.556 16.227 44 24 44z" />
      <path fill="#1976D2" d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.084 5.571l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z" />
    </svg>
  );
}

const getPasswordChecks = (password) => ({
  length: password.length >= 8,
  lowercase: /[a-z]/.test(password),
  uppercase: /[A-Z]/.test(password),
  number: /\d/.test(password),
  special: /[^A-Za-z0-9]/.test(password),
});

const getStrengthMeta = (checks) => {
  const passed = Object.values(checks).filter(Boolean).length;
  if (passed <= 1) return { label: "Very weak", color: "bg-red-500", width: "w-1/5" };
  if (passed === 2) return { label: "Weak", color: "bg-orange-500", width: "w-2/5" };
  if (passed === 3) return { label: "Fair", color: "bg-yellow-500", width: "w-3/5" };
  if (passed === 4) return { label: "Good", color: "bg-lime-600", width: "w-4/5" };
  return { label: "Strong", color: "bg-green-600", width: "w-full" };
};

export default function AuthModal({ isOpen, onClose }) {
  const { signInWithPassword, signUpWithPassword, signInWithGoogle } = useAuth();
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const passwordChecks = getPasswordChecks(password);
  const passwordStrength = getStrengthMeta(passwordChecks);
  const passwordValid = Object.values(passwordChecks).every(Boolean);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    setMessage("");

    try {
      if (mode === "signup" && !passwordValid) {
        setError("Password does not meet all requirements.");
        return;
      }

      const action = mode === "signin" ? signInWithPassword(email, password) : signUpWithPassword(email, password);
      const { data, error: authError } = await action;

      if (authError) {
        setError(authError.message);
        return;
      }

      if (mode === "signup" && !data?.session) {
        setMessage("Account created. Check your email to confirm your account.");
      } else {
        onClose();
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleGoogle = async () => {
    setError("");
    setMessage("");
    setSubmitting(true);
    const { error: oauthError } = await signInWithGoogle();
    if (oauthError) {
      setError(oauthError.message);
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[120] flex items-center justify-center px-4">
      <button className="absolute inset-0 bg-black/45" onClick={onClose} aria-label="Close auth dialog" />
      <div className="relative w-full max-w-md rounded-2xl bg-[#f8f1e0] border border-[#162b4a]/20 shadow-2xl p-6">
        <button
          className="absolute top-4 right-4 text-slate-500 hover:text-slate-900 transition-colors"
          onClick={onClose}
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <h3 className="text-2xl font-serif text-slate-900 mb-2">
          {mode === "signin" ? "Sign In" : "Create Account"}
        </h3>
        <p className="text-sm text-slate-500 mb-6">
          {mode === "signin" ? "Access personalized recommendations." : "Create an account to save your preferences."}
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-xl border border-[#162b4a]/20 bg-white px-4 py-3 text-sm outline-none focus:border-[#d4af37]"
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-xl border border-[#162b4a]/20 bg-white px-4 py-3 text-sm outline-none focus:border-[#d4af37]"
            minLength={6}
            required
          />

          {mode === "signup" ? (
            <div className="rounded-xl border border-[#162b4a]/15 bg-white/70 px-4 py-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-slate-700">Password strength</span>
                <span className="text-xs text-slate-600">{passwordStrength.label}</span>
              </div>
              <div className="h-2 rounded-full bg-slate-200 overflow-hidden mb-3">
                <div className={`h-full transition-all duration-300 ${passwordStrength.color} ${passwordStrength.width}`} />
              </div>
              <ul className="text-xs space-y-1 text-slate-600">
                <li className={passwordChecks.length ? "text-green-700" : ""}>- At least 8 characters</li>
                <li className={passwordChecks.uppercase ? "text-green-700" : ""}>- One uppercase letter</li>
                <li className={passwordChecks.lowercase ? "text-green-700" : ""}>- One lowercase letter</li>
                <li className={passwordChecks.number ? "text-green-700" : ""}>- One number</li>
                <li className={passwordChecks.special ? "text-green-700" : ""}>- One special character</li>
              </ul>
            </div>
          ) : null}

          {error ? <p className="text-sm text-red-700">{error}</p> : null}
          {message ? <p className="text-sm text-green-700">{message}</p> : null}

          <button
            type="submit"
            disabled={submitting || (mode === "signup" && !passwordValid)}
            className="w-full rounded-xl bg-[#162b4a] text-white py-3 text-sm font-semibold hover:bg-[#1f3a60] transition-colors disabled:opacity-60"
          >
            {submitting ? "Please wait..." : mode === "signin" ? "Sign In" : "Create Account"}
          </button>
        </form>

        <button
          onClick={handleGoogle}
          disabled={submitting}
          className="w-full mt-3 rounded-xl border border-[#162b4a]/20 bg-white py-3 text-sm font-medium text-slate-800 hover:bg-slate-50 transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
        >
          <GoogleIcon />
          Continue with Google
        </button>

        <button
          onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
          className="w-full mt-4 text-sm text-[#162b4a] hover:text-[#1f3a60] underline"
        >
          {mode === "signin" ? "Need an account? Sign up" : "Already have an account? Sign in"}
        </button>
      </div>
    </div>
  );
}
