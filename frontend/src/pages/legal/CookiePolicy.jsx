/**
 * CookiePolicy.jsx — Cookie Policy Page
 * Last Updated: September 10, 2026
 */

import React from 'react';
import { Link } from 'react-router-dom';

function CookiePolicy() {
  return (
    <div style={{ backgroundColor: 'var(--color-background)', minHeight: '100vh', padding: '2rem 1rem' }}>
      <div className="container mx-auto max-w-4xl" style={{ backgroundColor: 'var(--color-surface)', borderRadius: '1rem', padding: '3rem', border: '1px solid var(--color-border)' }}>
        <Link to="/" style={{ color: 'var(--color-primary)', textDecoration: 'none', fontSize: '0.875rem', marginBottom: '2rem', display: 'inline-block' }}>
          ← Back to Home
        </Link>

        <h1 style={{ fontSize: '2.25rem', fontWeight: 800, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
          Cookie Policy
        </h1>
        <p style={{ color: 'var(--color-text-secondary)', marginBottom: '2rem' }}>
          Last Updated: September 10, 2026
        </p>

        <div style={{ color: 'var(--color-text-secondary)', lineHeight: 1.8, fontSize: '0.9375rem' }}>
          <section style={{ marginBottom: '2rem', backgroundColor: 'var(--color-success-bg)', padding: '1.5rem', borderRadius: '0.5rem', border: '1px solid var(--color-success-border)' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              Good News: We Don't Use Cookies
            </h2>
            <p style={{ fontWeight: 600 }}>
              Gmail Manager does not use tracking or advertising cookies. We do not use analytics services like Google Analytics, Facebook Pixel, or any third-party tracking tools.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              What We Use Instead
            </h2>
            <p style={{ marginBottom: '1rem' }}>
              We use browser storage technologies that are strictly necessary for the application to function:
            </p>
            <ul style={{ paddingLeft: '1.5rem', marginBottom: '1rem' }}>
              <li><strong>localStorage:</strong> Stores your session token to keep you logged in between visits</li>
              <li><strong>sessionStorage:</strong> Temporarily stores OAuth flow state during Google authentication</li>
            </ul>
            <p>
              These storage mechanisms are essential for authentication and cannot be disabled without breaking the login functionality.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              Third-Party Services
            </h2>
            <p style={{ marginBottom: '1rem' }}>
              While we don't use cookies ourselves, the following third-party services may collect data:
            </p>
            <ul style={{ paddingLeft: '1.5rem', marginBottom: '1rem' }}>
              <li><strong>Google OAuth 2.0:</strong> Used for authentication — subject to Google's privacy policy</li>
              <li><strong>Google Fonts:</strong> May log your IP address when loading fonts — subject to Google's privacy policy</li>
            </ul>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              No Cookie Consent Banner Required
            </h2>
            <p>
              Under GDPR and ePrivacy Directive, cookie consent banners are only required for non-essential cookies. Since we only use strictly necessary storage for authentication, no consent banner is legally required.
            </p>
          </section>

          <section style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              Future Changes
            </h2>
            <p style={{ marginBottom: '1rem', fontWeight: 600, color: 'var(--color-warning)' }}>
              If we ever add analytics or tracking in the future, we will:
            </p>
            <ul style={{ paddingLeft: '1.5rem' }}>
              <li>Update this Cookie Policy</li>
              <li>Implement a cookie consent banner</li>
              <li>Obtain your explicit consent before enabling tracking</li>
              <li>Provide opt-out mechanisms</li>
            </ul>
          </section>

          <section>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '1rem' }}>
              Contact Us
            </h2>
            <p>
              Questions about our cookie usage? Contact:<br />
              <strong>Email:</strong> legal@gmailmanager.com
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}

export default CookiePolicy;
