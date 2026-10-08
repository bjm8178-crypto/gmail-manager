/**
 * TermsOfService.jsx — Terms of Service Page
 * Last Updated: September 10, 2026
 */

import React from 'react';
import { Link } from 'react-router-dom';

function TermsOfService() {
  return (
    <div style={{ backgroundColor: 'var(--color-background)', minHeight: '100vh', padding: '2rem 1rem' }}>
      <div className="container mx-auto max-w-4xl" style={{ backgroundColor: 'var(--color-surface)', borderRadius: '1rem', padding: '3rem', border: '1px solid var(--color-border)' }}>
        <Link to="/" style={{ color: 'var(--color-primary)', textDecoration: 'none', fontSize: '0.875rem', marginBottom: '2rem', display: 'inline-block' }}>
          ← Back to Home
        </Link>

        <h1 style={{ fontSize: '2.25rem', fontWeight: 800, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
          Terms of Service
        </h1>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: '2rem' }}>
          Last Updated: September 10, 2026
        </p>

        <div style={{ color: 'var(--color-text-secondary)', lineHeight: 1.8, fontSize: '0.9375rem' }}>
          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              1. Acceptance of Terms
            </h2>
            <p>
              By accessing and using Gmail Manager, you accept and agree to be bound by these Terms of Service. If you do not agree, do not use the service.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              2. Service Description
            </h2>
            <p style={{ marginBottom: '1rem' }}>
              Gmail Manager provides AI-powered email classification, scam detection, and management tools. The service includes:
            </p>
            <ul style={{ paddingLeft: '1.5rem' }}>
              <li>Automatic email labeling using AI</li>
              <li>Scam risk scoring (0-100 scale)</li>
              <li>URL safety scanning</li>
              <li>Email rewriting capabilities</li>
              <li>Quarantine management</li>
            </ul>
          </section>

          <section style={{ marginBottom: '2rem', backgroundColor: 'var(--color-warning-bg)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid var(--color-warning-border)' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              3. No Warranty — AI Accuracy Disclaimer
            </h2>
            <p style={{ marginBottom: '1rem', fontWeight: 600 }}>
              <strong>IMPORTANT:</strong> Gmail Manager's scam detection and risk scoring are automated AI estimates, not guarantees.
            </p>
            <p style={{ marginBottom: '1rem' }}>
              The Service is provided "AS IS" without warranties of any kind. We do not guarantee that:
            </p>
            <ul style={{ paddingLeft: '1.5rem', marginBottom: '1rem' }}>
              <li>AI scam detection will identify all threats (false negatives possible)</li>
              <li>Legitimate emails won't be flagged as suspicious (false positives possible)</li>
              <li>The service will be error-free, uninterrupted, or 100% available</li>
              <li>AI-generated labels or classifications are accurate</li>
            </ul>
            <p style={{ fontWeight: 600 }}>
              You are responsible for verifying suspicious emails yourself before taking action. Gmail Manager is a tool to assist, not replace, your own judgment.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              4. User Responsibilities
            </h2>
            <p style={{ marginBottom: '1rem' }}>
              You agree to:
            </p>
            <ul style={{ paddingLeft: '1.5rem' }}>
              <li>Provide accurate information during registration</li>
              <li>Keep your account credentials secure</li>
              <li>Use the service in compliance with applicable laws</li>
              <li>Not attempt to reverse engineer, hack, or abuse the service</li>
              <li>Not use the service for illegal activities</li>
            </ul>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              5. API Keys and Third-Party Services
            </h2>
            <p>
              You may provide your own API keys for AI providers (Groq, Gemini, Cohere, NVIDIA). You are responsible for usage costs and compliance with those providers' terms.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              6. Limitation of Liability
            </h2>
            <p>
              To the maximum extent permitted by law, Gmail Manager and its operators shall not be liable for any indirect, incidental, special, consequential, or punitive damages, including loss of data, loss of profits, or business interruption.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              7. Account Termination
            </h2>
            <p>
              We reserve the right to suspend or terminate your account for violations of these Terms or for any reason with notice.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              8. Open Source and Hosted Service
            </h2>
            <p>
              The Gmail Manager source code is licensed under the MIT License. However, these Terms govern the use of our hosted service, which is separate from the open-source code license.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              9. Changes to Terms
            </h2>
            <p>
              We may modify these Terms at any time. Continued use after changes constitutes acceptance of modified Terms.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              10. Contact
            </h2>
            <p>
              For questions about these Terms, contact:<br />
              <strong>Email:</strong> legal@gmailmanager.com
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

export default TermsOfService;
