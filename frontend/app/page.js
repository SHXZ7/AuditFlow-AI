"use client";

import axios from "axios";
import { useState, useEffect } from "react";

export default function Home() {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    company: "",
    website: "",
    notes: "",
  });

  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");
  const [leadId, setLeadId] = useState(null);
  const [polling, setPolling] = useState(false);

  // URL validation function (mirrors backend logic)
  const isValidUrl = (url) => {
    if (!url.trim()) return { valid: false, message: "Website is required" };

    // Check if it looks like a domain
    const urlPattern = /^(https?:\/\/)?(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)$/;
    
    if (!urlPattern.test(url)) {
      return { valid: false, message: "Invalid URL format (must contain a domain, e.g., example.com)" };
    }

    return { valid: true, message: "" };
  };

  const handleChange = (e) => {
    setSuccess(false);
    setError("");
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  // Poll backend for lead status
  useEffect(() => {
    if (!leadId || !polling) return;

    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(`http://127.0.0.1:8000/api/leads/${leadId}`);
        const { status, error: backendError, error_type } = response.data;

        if (status === "validation_failed") {
          setError(backendError || "URL validation failed on the server");
          setPolling(false);
        } else if (status === "completed") {
          setSuccess(true);
          setError("");
          setPolling(false);
          clearInterval(pollInterval);
        }
      } catch (err) {
        console.error("Poll error:", err);
        setPolling(false);
        clearInterval(pollInterval);
      }
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(pollInterval);
  }, [leadId, polling]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    // Client-side URL validation
    const urlValidation = isValidUrl(formData.website);
    if (!urlValidation.valid) {
      setError(urlValidation.message);
      return;
    }

    try {
      setLoading(true);
      const response = await axios.post("http://127.0.0.1:8000/api/leads", formData);
      const newLeadId = response.data.lead_id;
      setLeadId(newLeadId);
      setPolling(true);
      setFormData({ name: "", email: "", company: "", website: "", notes: "" });
    } catch (error) {
      console.error(error);
      setError("Failed to submit form. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;1,9..40,300&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        .root {
          min-height: 100vh;
          background-color: #0c0c0b;
          background-image:
            radial-gradient(ellipse 60% 50% at 20% 0%, rgba(180,155,100,0.07) 0%, transparent 60%),
            radial-gradient(ellipse 40% 60% at 80% 100%, rgba(100,140,130,0.06) 0%, transparent 55%);
          font-family: 'DM Sans', sans-serif;
          color: #f0ece4;
          display: flex;
          align-items: center;
          padding: 3rem 2rem;
        }

        .inner {
          max-width: 1140px;
          width: 100%;
          margin: 0 auto;
          display: grid;
          grid-template-columns: 1fr 420px;
          gap: 6rem;
          align-items: center;
        }

        /* ── Left column ── */
        .eyebrow {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          font-size: 11px;
          font-weight: 500;
          letter-spacing: 0.18em;
          text-transform: uppercase;
          color: #b49b64;
          margin-bottom: 2rem;
        }
        .eyebrow::before {
          content: '';
          display: block;
          width: 28px;
          height: 1px;
          background: #b49b64;
          flex-shrink: 0;
        }

        .headline {
          font-family: 'DM Serif Display', serif;
          font-size: clamp(3rem, 6vw, 5.2rem);
          line-height: 1.0;
          letter-spacing: -0.01em;
          color: #f0ece4;
          margin-bottom: 1.75rem;
        }
        .headline em {
          font-style: italic;
          color: #b49b64;
        }

        .subtext {
          font-size: 1rem;
          font-weight: 300;
          line-height: 1.75;
          color: #9a9488;
          max-width: 440px;
          margin-bottom: 3rem;
        }

        .stats-row {
          display: flex;
          gap: 0;
          border: 1px solid rgba(255,255,255,0.07);
          border-radius: 2px;
          overflow: hidden;
          max-width: 400px;
          margin-bottom: 3rem;
        }
        .stat {
          flex: 1;
          padding: 1.1rem 1.25rem;
          border-right: 1px solid rgba(255,255,255,0.07);
        }
        .stat:last-child { border-right: none; }
        .stat-num {
          font-family: 'DM Serif Display', serif;
          font-size: 1.5rem;
          color: #f0ece4;
          line-height: 1;
        }
        .stat-label {
          font-size: 11px;
          font-weight: 400;
          letter-spacing: 0.08em;
          color: #6b6760;
          margin-top: 4px;
          text-transform: uppercase;
        }

        .tags {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
        .tag {
          font-size: 12px;
          font-weight: 400;
          letter-spacing: 0.05em;
          color: #7a756e;
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 2px;
          padding: 6px 14px;
        }

        /* ── Right column / form ── */
        .card {
          background: #f5f1eb;
          border-radius: 4px;
          padding: 2.5rem 2.25rem;
          position: relative;
          overflow: hidden;
        }
        .card::before {
          content: '';
          position: absolute;
          top: 0; left: 0; right: 0;
          height: 3px;
          background: linear-gradient(90deg, #b49b64 0%, #8fa89e 100%);
        }

        .card-eyebrow {
          font-size: 10px;
          font-weight: 500;
          letter-spacing: 0.2em;
          text-transform: uppercase;
          color: #b49b64;
          margin-bottom: 0.5rem;
        }
        .card-title {
          font-family: 'DM Serif Display', serif;
          font-size: 1.85rem;
          color: #1a1814;
          line-height: 1.15;
          margin-bottom: 0.5rem;
        }
        .card-desc {
          font-size: 13px;
          font-weight: 300;
          color: #7a7068;
          margin-bottom: 1.75rem;
          line-height: 1.6;
        }

        .success-box {
          background: #eef5f0;
          border: 1px solid #c2dbc8;
          border-radius: 3px;
          padding: 1rem 1.1rem;
          margin-bottom: 1.25rem;
        }
        .success-title {
          font-size: 13px;
          font-weight: 500;
          color: #2d5c38;
          margin-bottom: 3px;
        }
        .success-body {
          font-size: 12px;
          font-weight: 300;
          color: #4f7e5a;
        }

        .error-box {
          background: #ffe8e8;
          border: 1px solid #d9999a;
          border-radius: 3px;
          padding: 1rem 1.1rem;
          margin-bottom: 1.25rem;
        }
        .error-title {
          font-size: 13px;
          font-weight: 500;
          color: #8b3d3d;
          margin-bottom: 3px;
        }
        .error-body {
          font-size: 12px;
          font-weight: 300;
          color: #a86767;
        }

        .field.error-field {
          border-color: #d9999a;
          box-shadow: 0 0 0 3px rgba(217, 153, 154, 0.12);
        }
        .field.error-field:focus {
          border-color: #d9999a;
          box-shadow: 0 0 0 3px rgba(217, 153, 154, 0.12);
        }

        .form { display: flex; flex-direction: column; gap: 10px; }

        .input-wrap {
          position: relative;
        }

        .field {
          width: 100%;
          background: #fff;
          border: 1px solid #e0dbd2;
          border-radius: 3px;
          padding: 13px 14px;
          font-family: 'DM Sans', sans-serif;
          font-size: 13.5px;
          font-weight: 300;
          color: #1a1814;
          outline: none;
          transition: border-color 0.15s, box-shadow 0.15s;
          appearance: none;
          -webkit-appearance: none;
        }
        .field::placeholder { color: #b8b2a9; }
        .field:focus {
          border-color: #b49b64;
          box-shadow: 0 0 0 3px rgba(180,155,100,0.12);
        }

        textarea.field {
          height: 90px;
          resize: none;
        }

        .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }

        .submit {
          width: 100%;
          background: #1a1814;
          color: #f0ece4;
          border: none;
          border-radius: 3px;
          padding: 15px 20px;
          font-family: 'DM Sans', sans-serif;
          font-size: 13px;
          font-weight: 500;
          letter-spacing: 0.06em;
          cursor: pointer;
          transition: background 0.15s, transform 0.1s;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 10px;
          margin-top: 4px;
        }
        .submit:hover:not(:disabled) { background: #2e2b24; }
        .submit:active:not(:disabled) { transform: scale(0.99); }
        .submit:disabled { opacity: 0.6; cursor: not-allowed; }

        .spinner {
          width: 16px; height: 16px;
          border: 1.5px solid rgba(240,236,228,0.25);
          border-top-color: #f0ece4;
          border-radius: 50%;
          animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .footer-note {
          text-align: center;
          font-size: 11px;
          font-weight: 300;
          color: #b0aa9f;
          margin-top: 10px;
          letter-spacing: 0.03em;
        }

        /* ── Decorative number ── */
        .deco-num {
          position: absolute;
          bottom: -1.5rem;
          right: -0.5rem;
          font-family: 'DM Serif Display', serif;
          font-size: 9rem;
          line-height: 1;
          color: rgba(180,155,100,0.05);
          pointer-events: none;
          user-select: none;
        }

        /* ── Responsive ── */
        @media (max-width: 860px) {
          .inner {
            grid-template-columns: 1fr;
            gap: 3rem;
          }
          .root { padding: 2.5rem 1.25rem; }
          .headline { font-size: 3rem; }
        }
      `}</style>

      <main className="root">
        <div className="inner">

          {/* ── Left ── */}
          <div>
            <div className="eyebrow">AI-Powered Audit</div>

            <h1 className="headline">
              Grow smarter.<br />
              <em>Audit first.</em>
            </h1>

            <p className="subtext">
              A focused AI analysis of your business — conversion opportunities, automation wins, and a premium growth report delivered to your inbox.
            </p>

            <div className="stats-row">
              <div className="stat">
                <div className="stat-num">10pt</div>
                <div className="stat-label">Scorecard</div>
              </div>
              <div className="stat">
                <div className="stat-num">PDF</div>
                <div className="stat-label">Report</div>
              </div>
              <div className="stat">
                <div className="stat-num">AI</div>
                <div className="stat-label">Insights</div>
              </div>
            </div>

            <div className="tags">
              <span className="tag">Conversion review</span>
              <span className="tag">Automation ideas</span>
              <span className="tag">Startup-grade summary</span>
            </div>
          </div>

          {/* ── Right / Form ── */}
          <div className="card">
            <div className="deco-num">AI</div>

            <div className="card-eyebrow">Free preview</div>
            <h2 className="card-title">Generate your report</h2>
            <p className="card-desc">Enter your details — we'll email a polished growth audit.</p>

            {success && (
              <div className="success-box">
                <div className="success-title">Audit generation started.</div>
                <div className="success-body">Your report will be delivered to your inbox shortly.</div>
              </div>
            )}

            {error && (
              <div className="error-box">
                <div className="error-title">Unable to proceed</div>
                <div className="error-body">{error}</div>
              </div>
            )}

            <form className="form" onSubmit={handleSubmit}>
              <div className="row">
                <input
                  className="field"
                  name="name"
                  value={formData.name}
                  placeholder="Your name"
                  onChange={handleChange}
                  required
                />
                <input
                  className="field"
                  name="email"
                  type="email"
                  value={formData.email}
                  placeholder="Work email"
                  onChange={handleChange}
                  required
                />
              </div>

              <div className="row">
                <input
                  className="field"
                  name="company"
                  value={formData.company}
                  placeholder="Company"
                  onChange={handleChange}
                  required
                />
                <input
                  className={`field ${error && error.includes("URL") ? "error-field" : ""}`}
                  name="website"
                  value={formData.website}
                  placeholder="Website"
                  onChange={handleChange}
                  required
                />
              </div>

              <textarea
                className="field"
                name="notes"
                value={formData.notes}
                placeholder="Anything we should know? (optional)"
                onChange={handleChange}
              />

              <button className="submit" disabled={loading}>
                {loading && <span className="spinner" />}
                {loading ? "Generating audit…" : "Generate AI Growth Audit"}
              </button>

              <p className="footer-note">No spam — just a focused AI growth snapshot.</p>
            </form>
          </div>

        </div>
      </main>
    </>
  );
}
