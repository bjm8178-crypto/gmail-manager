/**
 * PrivacyPolicy.jsx — Privacy Policy Page
 * GDPR & CCPA Compliant Privacy Notice
 * Last Updated: September 10, 2026
 */

import React from 'react';
import { Link } from 'react-router-dom';

function PrivacyPolicy() {
  return (
    <div style={{ backgroundColor: 'var(--color-background)', minHeight: '100vh', padding: '2rem 1rem' }}>
      <div className="container mx-auto max-w-4xl" style={{ backgroundColor: 'var(--color-surface)', borderRadius: '1rem', padding: '3rem', border: '1px solid var(--color-border)' }}>
        <Link to="/" style={{ color: 'var(--color-primary)', textDecoration: 'none', fontSize: '0.875rem', marginBottom: '2rem', display: 'inline-block' }}>
          ← Back to Home
        </Link>

        <h1 style={{ fontSize: '2.25rem', fontWeight: 800, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
          Privacy Policy
        </h1>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: '2rem' }}>
          Last Updated: September 10, 2026
        </p>

        <div style={{ color: 'var(--color-text-secondary)', lineHeight: 1.8, fontSize: '0.9375rem' }}>
          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              1. Information We Collect
            </h2>
            <p style={{ marginBottom: '1rem' }}>
              When you use Gmail Manager, we collect and process:
            </p>
            <ul style={{ paddingLeft: '1.5rem', marginBottom: '1rem' }}>
              <li>Gmail OAuth token (via Google OAuth 2.0) to access your email</li>
              <li>Email metadata and content for AI classification and scam detection</li>
              <li>Custom labels you create within the application</li>
              <li>API keys for AI providers (encrypted using Fernet/AES-256 and stored in our database)</li>
              <li>Usage data and error logs for service improvement</li>
            </ul>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              2. How We Use Your Information
            </h2>
            <p style={{ marginBottom: '1rem' }}>
              We process your data for the following purposes:
            </p>
            <ul style={{ paddingLeft: '1.5rem', marginBottom: '1rem' }}>
              <li>To provide email classification, labeling, and scam detection services</li>
              <li>To process your emails through AI providers for analysis</li>
              <li>To check URLs against Google Safe Browsing API for security</li>
              <li>To improve our services and user experience</li>
              <li>To maintain security and prevent abuse</li>
            </ul>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              3. Data Storage and Security
            </h2>
            <p style={{ marginBottom: '1rem' }}>
              <strong>Hosted Version:</strong> Email data is stored in a PostgreSQL database hosted on Railway. API keys are encrypted at rest using Fernet/AES-256 encryption.
            </p>
            <p style={{ marginBottom: '1rem' }}>
              <strong>Self-Hosted Version:</strong> All data remains on your local machine in a SQLite database.
            </p>
            <p style={{ marginBottom: '1rem' }}>
              We implement industry-standard security measures including encryption, secure authentication, and regular security audits.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              4. Third-Party Data Sharing
            </h2>
            <p style={{ marginBottom: '1rem' }}>
              Your email content is shared with the following third parties for processing:
            </p>
            <ul style={{ paddingLeft: '1.5rem', marginBottom: '1rem' }}>
              <li><strong>Groq</strong> — Primary AI provider for email classification</li>
              <li><strong>Google Gemini</strong> — Secondary AI provider (automatic failover)</li>
              <li><strong>Cohere</strong> — Tertiary AI provider (automatic failover)</li>
              <li><strong>Google Safe Browsing API</strong> — URL security scanning</li>
              <li><strong>Google Fonts</strong> — Font delivery (visitor IP addresses shared)</li>
            </ul>
            <p>
              We do not sell your personal data to third parties.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              5. Data Retention
            </h2>
            <p>
              We retain your data for as long as your account is active. URL safety results are cached for 24 hours. You can request deletion of your data at any time by contacting us.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              6. Your Rights (GDPR & CCPA)
            </h2>
            <p style={{ marginBottom: '1rem' }}>
              You have the right to:
            </p>
            <ul style={{ paddingLeft: '1.5rem', marginBottom: '1rem' }}>
              <li><strong>Access:</strong> Request a copy of your personal data</li>
              <li><strong>Rectification:</strong> Correct inaccurate personal data</li>
              <li><strong>Erasure:</strong> Request deletion of your personal data</li>
              <li><strong>Portability:</strong> Receive your data in a machine-readable format</li>
              <li><strong>Object:</strong> Object to processing of your personal data</li>
              <li><strong>Opt-Out:</strong> California residents can opt-out of data sharing</li>
            </ul>
            <p>
              To exercise these rights, contact us at <strong>legal@gmailmanager.com</strong>
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              7. International Data Transfers
            </h2>
            <p>
              Your data may be transferred to and processed in countries outside your residence. We ensure appropriate safeguards are in place for international transfers.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              8. Cookies and Tracking
            </h2>
            <p>
              We do not use tracking or advertising cookies. We use localStorage and sessionStorage (strictly necessary for authentication) to keep you logged in.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              9. Data Controller
            </h2>
            <p>
              <strong>Gmail Manager</strong><br />
              Email: legal@gmailmanager.com<br />
              [Registered Address To Be Added]
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              10. Changes to This Policy
            </h2>
            <p>
              We may update this Privacy Policy from time to time. We will notify you of significant changes by email or through the application.
            </p>
          </section>

          <section>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              11. Contact Us
            </h2>
            <p>
              For questions about this Privacy Policy or to exercise your rights, contact:<br />
              <strong>Email:</strong> legal@gmailmanager.com
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

export default PrivacyPolicy;
