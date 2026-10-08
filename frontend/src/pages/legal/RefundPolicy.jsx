/**
 * RefundPolicy.jsx — Refund Policy Page
 * Last Updated: September 10, 2026
 */

import React from 'react';
import { Link } from 'react-router-dom';

function RefundPolicy() {
  return (
    <div style={{ backgroundColor: 'var(--color-background)', minHeight: '100vh', padding: '2rem 1rem' }}>
      <div className="container mx-auto max-w-4xl" style={{ backgroundColor: 'var(--color-surface)', borderRadius: '1rem', padding: '3rem', border: '1px solid var(--color-border)' }}>
        <Link to="/" style={{ color: 'var(--color-primary)', textDecoration: 'none', fontSize: '0.875rem', marginBottom: '2rem', display: 'inline-block' }}>
          ← Back to Home
        </Link>

        <h1 style={{ fontSize: '2.25rem', fontWeight: 800, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
          Refund Policy
        </h1>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: '2rem' }}>
          Last Updated: September 10, 2026
        </p>

        <div style={{ color: 'var(--color-text-secondary)', lineHeight: 1.8, fontSize: '0.9375rem' }}>
          <section style={{ marginBottom: '2rem', backgroundColor: 'var(--color-info-bg)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid var(--color-info-border)' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              Currently Free to Use
            </h2>
            <p style={{ fontWeight: 600 }}>
              Gmail Manager is currently free to use. No payments are processed at this time.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              Open Source Project
            </h2>
            <p>
              Gmail Manager is an open-source project licensed under the MIT License. You can self-host the application at no cost, or use our hosted version.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              Future Paid Features
            </h2>
            <p style={{ marginBottom: '1rem' }}>
              If we introduce paid features in the future, this policy will be updated to include:
            </p>
            <ul style={{ paddingLeft: '1.5rem', marginBottom: '1rem' }}>
              <li>Refund eligibility criteria</li>
              <li>Refund request process</li>
              <li>Timeframes for refund processing</li>
              <li>Conditions for refund approval/denial</li>
            </ul>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              Third-Party API Costs
            </h2>
            <p>
              If you use your own API keys (Groq, Gemini, Cohere, NVIDIA), you are responsible for any usage charges from those providers. Gmail Manager does not charge for or refund third-party API costs.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              Contact Us
            </h2>
            <p>
              Questions about billing or refunds? Contact:<br />
              <strong>Email:</strong> legal@gmailmanager.com
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

export default RefundPolicy;
