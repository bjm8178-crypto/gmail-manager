/**
 * EmailBodyFrame.jsx — Isolated Email Body Renderer
 * 
 * Renders email bodies faithfully like Gmail:
 * - HTML bodies: sandboxed <iframe> with no script execution
 * - Plain text: <div> with proper word wrapping
 * - Auto-sizes iframe height from content (max 2000px)
 * - All links open in new tab via <base target="_blank">
 * - Sender CSS/markup fully isolated from app
 * - Theme-aware: respects light/dark mode (FIXED 2026-09-11)
 * - Mobile: horizontal scroll for wide table-based emails (FIXED 2026-09-14)
 */

import React, { useRef, useEffect, useState } from 'react';

import { emailCsp, cleanEmailMarkup } from '../utils/emailPrivacy';

function EmailBodyFrame({ body, className = '', textStyle = {} }) {
  const iframeRef = useRef(null);
  const [consentedBody, setConsentedBody] = useState(null);
  const loadImages = consentedBody === body;

  // Detect if body contains HTML tags
  const looksLikeHTML = (text) => {
    if (!text) return false;
    return /<[a-z][\s\S]*>/i.test(text);
  };

  const isHTML = looksLikeHTML(body);

  // Get current theme colors from CSS variables
  const getThemeColors = () => {
    const root = document.documentElement;
    const computed = getComputedStyle(root);
    
    const background = computed.getPropertyValue('--color-surface').trim() || '#ffffff';
    const text = computed.getPropertyValue('--color-text-primary').trim() || '#1a1a1a';
    
    const isDark = isColorDark(background);
    
    return {
      background,
      text,
      border: computed.getPropertyValue('--color-border').trim() || '#e5e7eb',
      link: computed.getPropertyValue('--color-primary').trim() || '#2563eb',
      isDark,
    };
  };
  
  // Helper to detect if a color is dark
  const isColorDark = (color) => {
    const hex = color.replace('#', '');
    const r = parseInt(hex.substr(0, 2), 16);
    const g = parseInt(hex.substr(2, 2), 16);
    const b = parseInt(hex.substr(4, 2), 16);
    const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return luminance < 0.5;
  };

  // Auto-resize iframe to fit content
  useEffect(() => {
    if (!isHTML || !iframeRef.current) return;

    const measure = () => {
      try {
        const iframe = iframeRef.current;
        if (!iframe || !iframe.contentDocument) return;

        const contentHeight = iframe.contentDocument.body?.scrollHeight || 0;
        iframe.style.height = `${Math.min(contentHeight + 20, 2000)}px`;
      } catch (err) {
        console.debug('[EmailBodyFrame] Could not measure iframe height:', err);
      }
    };

    const iframe = iframeRef.current;
    if (iframe) {
      iframe.addEventListener('load', measure);
      const resizeInterval = setInterval(measure, 500);
      
      return () => {
        iframe.removeEventListener('load', measure);
        clearInterval(resizeInterval);
      };
    }
  }, [isHTML, body]);

  // HTML body - render in sandboxed iframe
  if (isHTML) {
    const colors = getThemeColors();
    
    const iframeContent = `
      <!DOCTYPE html>
      <html>
        <head>
          <meta http-equiv="Content-Security-Policy" content="${emailCsp(loadImages)}">
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <base target="_blank">
          <style>
            html, body {
              margin: 0;
              padding: 0;
              background: ${colors.background};
              color: ${colors.text};
            }
            body {
              padding: 16px;
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
              font-size: 14px;
              line-height: 1.6;
              word-wrap: break-word;
              overflow-wrap: anywhere;
              -webkit-text-size-adjust: 100%;
            }
            img {
              max-width: 100%;
              height: auto;
            }
            table {
              max-width: 100%;
            }
            a {
              color: ${colors.link};
              text-decoration: underline;
            }
            * {
              box-sizing: border-box;
            }
            /* Allow tables with explicit widths to scroll horizontally */
            table[width], table[style*="width"] {
              max-width: none;
            }
          </style>
        </head>
        <body>
          ${cleanEmailMarkup(body)}
        </body>
      </html>
    `;

    return (
      <div
        style={{
          background: 'var(--color-surface)',
          borderRadius: '8px',
          overflow: 'hidden',
          border: '1px solid var(--color-border)',
        }}
      >
        <div className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-secondary)' }}>
          {loadImages ? 'External images enabled for this message.' : 'External images are blocked to prevent tracking.'}
          <button type="button" className="ml-3 underline py-2" onClick={() => setConsentedBody(loadImages ? null : body)}>
            {loadImages ? 'Block external images' : 'Load external images'}
          </button>
        </div>
        {/* Horizontal scroll wrapper for wide HTML emails on mobile */}
        <div
          style={{
            overflowX: 'auto',
            WebkitOverflowScrolling: 'touch',
          }}
        >
          <iframe
            ref={iframeRef}
            srcDoc={iframeContent}
            sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
            referrerPolicy="no-referrer"
            className={className}
            style={{
              width: '100%',
              border: 'none',
              display: 'block',
              minHeight: '200px',
              backgroundColor: 'var(--color-surface)',
            }}
            title="Email content"
          />
        </div>
      </div>
    );
  }

  // Plain text body - render with word wrapping
  return (
    <div
      className={className}
      style={{
        whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere',
        wordBreak: 'break-word',
        ...textStyle,
      }}
    >
      {body || 'No content available'}
    </div>
  );
}

export default EmailBodyFrame;
