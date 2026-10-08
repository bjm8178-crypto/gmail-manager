/**
 * LandingPage.jsx — Professional SaaS Marketing Page
 * Light Design System (Modern Minimalism + Soft Neumorphism + Premium SaaS + Subtle Motion)
 * Fixed for Complete Structural Mobile Responsiveness & Structured Website Content
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Mail, Shield, Zap, Brain, Lock, Server, CheckCircle,
  TrendingUp, Clock, Activity, Database, Eye, AlertCircle, Menu, X, ArrowRight, ArrowDown, Sun, Moon
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';

function LandingPage() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { theme, toggleTheme } = useTheme();

  // Shrink header padding on scroll
  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 20) {
        setScrolled(true);
      } else {
        setScrolled(false);
      }
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const features = [
    {
      icon: Mail,
      color: '--color-primary-light',
      title: '🏷️ Auto Labels',
      description: 'AI analyzes every email and applies colored Gmail labels — Work, Finance, Newsletter, and more — automatically.'
    },
    {
      icon: Shield,
      color: '--color-danger',
      title: '🛡️ Scam Shield',
      description: 'Detects phishing indicators and scam patterns, then assigns a 0–100 risk score to every email.'
    },
    {
      icon: Eye,
      color: '--color-success',
      title: '🔗 URL Scanner',
      description: 'Every link in every email is checked against the Google Safe Browsing API for malware and phishing.'
    },
    {
      icon: Lock,
      color: '--color-warning',
      title: '🔒 Quarantine',
      description: 'Suspicious emails are auto-isolated with one-click Safe / Delete actions.'
    },
    {
      icon: Brain,
      color: '--color-primary-light',
      title: '✏️ AI Rewriter',
      description: 'Transform any email with presets — Professional, Shorten, Friendly — or a custom instruction.'
    },
    {
      icon: Database,
      color: '--color-info',
      title: '📊 Smart Filters',
      description: 'Server-side filtering by sender, label, or scam score, with debounced search.'
    },
    {
      icon: Activity,
      color: '--color-success',
      title: '🔄 AI Failover',
      description: 'Cascading fallback across Groq → Gemini → Cohere — automatic switch on rate limits. NVIDIA reserved for future use.'
    }
  ];

  const stats = [
    { value: '18', label: 'API Endpoints' },
    { value: '4', label: 'AI Providers' },
    { value: '0-100', label: 'Scam Risk Scoring' },
    { value: '24hr', label: 'URL Safety Cache' }
  ];

  const providers = [
    { key: 'groq', name: 'Groq API Key', desc: 'Primary AI provider — Groq LLaMA 3', status: 'Connected · Primary', type: 'Primary', color: '--color-success', pulse: true },
    { key: 'gemini', name: 'Gemini API Key', desc: 'Secondary AI provider — Google Gemini Flash', status: 'Connected · Secondary', type: 'Secondary', color: '--color-info', pulse: true },
    { key: 'cohere', name: 'Cohere API Key', desc: 'Tertiary AI provider — Cohere Command-R', status: 'Connected · Tertiary', type: 'Tertiary', color: '--color-warning', pulse: true },
    { key: 'nvidia', name: 'NVIDIA API Key', desc: 'Reserved provider (inactive, future use)', status: 'Reserved · Inactive', type: 'Inactive', color: '--color-text-muted', pulse: false }
  ];

  const steps = [
    { num: '[Step 1]', title: 'Connect', desc: 'Google OAuth 2.0 login, secure token flow' },
    { num: '[Step 2]', title: 'Fetch & Scan', desc: 'Gmail API pulls inbox, bulk AI analysis via SSE (live progress %)' },
    { num: '[Step 3]', title: 'Classify', desc: 'AI cascade labels + scores every email in real time' },
    { num: '[Step 4]', title: 'Protect', desc: 'High-risk emails auto-quarantined, links checked vs Safe Browsing' },
    { num: '[Step 5]', title: 'Act', desc: 'Rewrite, relabel, restore, or delete — all from one dashboard' }
  ];

  const securityChecklist = [
    'All credentials stored locally (.env) — never transmitted',
    'OAuth tokens auto-refreshed, stored in token.json',
    'URL safety results cached 24hrs in SQLite',
    'Emails never leave your machine — analysis runs on your own API keys',
    'Electron hardened: contextIsolation on, nodeIntegration off'
  ];

  return (
    <div style={{
      backgroundColor: 'var(--color-background)',
      minHeight: '100vh',
      touchAction: 'auto',
      WebkitTouchCallout: 'default',
      userSelect: 'text',
      width: '100%',
      maxWidth: '100%',
      boxSizing: 'border-box'
    }}>
      <style>{`
        /* UNDERLINE-SLIDE-IN ON HOVER for Nav Links */
        .nav-link-underline {
          position: relative;
          color: var(--color-text-secondary);
          text-decoration: none;
          font-size: 0.9375rem;
          font-weight: 500;
          transition: color var(--transition-fast);
        }
        .nav-link-underline::after {
          content: '';
          position: absolute;
          width: 100%;
          transform: scaleX(0);
          height: 2px;
          bottom: -4px;
          left: 0;
          background-color: 'var(--color-primary)';
          transform-origin: bottom right;
          transition: transform 0.25s ease-out;
        }
        .nav-link-underline:hover {
          color: 'var(--color-text-primary)';
        }
        .nav-link-underline:hover::after {
          transform: scaleX(1);
          transform-origin: bottom left;
        }

        /* CARD HOVER: lift + shadow, border glow blue, icon scales */
        .feature-card {
          background-color: 'var(--color-surface)';
          border-radius: 'var(--radius-lg)';
          padding: 2rem;
          border: 1px solid 'var(--color-border)';
          box-shadow: 'var(--shadow-sm)';
          transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
          display: flex;
          flex-direction: column;
          min-width: 0;
          box-sizing: border-box;
        }
        .feature-card:hover {
          transform: translateY(-4px);
          box-shadow: 'var(--shadow-md)';
          border-color: 'var(--color-primary)';
        }
        .feature-card:hover .feature-icon-container {
          transform: scale(1.1);
        }

        /* ANIONMATED GRADIENT GLOW BEHIND DASHBOARD MOCKUP */
        @keyframes pulseGlow {
          0%, 100% { opacity: 0.15; transform: scale(1.0); }
          50% { opacity: 0.3; transform: scale(1.08); }
        }
        .mockup-glow {
          position: absolute;
          filter: blur(80px);
          border-radius: 50%;
          background: radial-gradient(circle, #5b5ce2 0%, #7c3aed 70%);
          animation: pulseGlow 8s ease-in-out infinite;
        }

        /* PULSING GREEN/BLUE/YELLOW DOT FOR PROVIDERS */
        @keyframes dotPulse {
          0% { box-shadow: 0 0 0 0 rgba(39, 174, 114, 0.4); }
          70% { box-shadow: 0 0 0 6px rgba(39, 174, 114, 0); }
          100% { box-shadow: 0 0 0 0 rgba(39, 174, 114, 0); }
        }
        @keyframes dotPulseBlue {
          0% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4); }
          70% { box-shadow: 0 0 0 6px rgba(37, 99, 235, 0); }
          100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }
        }
        @keyframes dotPulseYellow {
          0% { box-shadow: 0 0 0 0 rgba(229, 162, 60, 0.4); }
          70% { box-shadow: 0 0 0 6px rgba(229, 162, 60, 0); }
          100% { box-shadow: 0 0 0 0 rgba(229, 162, 60, 0); }
        }
        .pulsing-dot-green {
          animation: dotPulse 2s infinite;
        }
        .pulsing-dot-blue {
          animation: dotPulseBlue 2s infinite;
        }
        .pulsing-dot-yellow {
          animation: dotPulseYellow 2s infinite;
        }

        /* SHIELD ICON SUBTLE PULSE GLOW */
        @keyframes shieldGlow {
          0%, 100% { filter: drop-shadow(0 0 2px rgba(39, 174, 114, 0.2)); }
          50% { filter: drop-shadow(0 0 15px rgba(39, 174, 114, 0.6)); }
        }
        .shield-animated {
          animation: shieldGlow 3s ease-in-out infinite;
        }
      `}</style>

      {/* 1. HEADER / NAVBAR */}
      <header
        style={{
          backgroundColor: scrolled ? 'rgba(var(--color-surface), 0.95)' : 'var(--color-surface)',
          borderBottom: '1px solid var(--color-border)',
          position: 'sticky',
          top: 0,
          zIndex: 50,
          width: '100%',
          maxWidth: '100%',
          boxSizing: 'border-box',
          transition: 'padding var(--transition-base), background-color var(--transition-base)'
        }}
        className={scrolled ? 'py-2 md:py-3 shadow-sm' : 'py-4 md:py-5'}
      >
        <div className="container mx-auto px-4 sm:px-6 w-full max-w-7xl flex items-center justify-between">
          {/* Logo Container */}
          <div className="flex items-center gap-2">
            <span role="img" aria-label="email" style={{ fontSize: '1.25rem' }}>📧</span>
            <span style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-text-primary)', letterSpacing: '-0.01em' }}>
              Gmail Manager
            </span>
          </div>

          {/* Desktop Nav Links & CTA */}
          <div className="hidden md:flex items-center gap-8">
            <a href="#features" className="nav-link-underline">Features</a>
            <a href="#architecture" className="nav-link-underline">Architecture</a>
            <a href="#security" className="nav-link-underline">Security</a>
            <a href="#api" className="nav-link-underline">API</a>
            
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="btn-secondary flex items-center gap-2"
              aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
            >
              {theme === 'light' ? (
                <Sun className="w-4 h-4" />
              ) : (
                <Moon className="w-4 h-4" />
              )}
              {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
            </button>
            
            <Link
              to="/login"
              className="hover-scale-cta text-white"
              style={{
                background: 'linear-gradient(135deg, var(--color-primary), var(--color-primary-hover))',
                padding: '0.625rem 1.5rem',
                borderRadius: '10px',
                textDecoration: 'none',
                fontWeight: 650,
                fontSize: '0.875rem',
                display: 'inline-block',
                transition: 'transform var(--transition-fast), box-shadow var(--transition-fast)'
              }}
            >
              Try Live Demo →
            </Link>
          </div>

          {/* Mobile Hamburger Button */}
          <button
            type="button"
            aria-label="Open navigation menu"
            aria-expanded={isMenuOpen}
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            className="md:hidden w-10 h-10 flex items-center justify-center rounded-lg transition-colors border border-transparent"
            style={{
              color: 'var(--color-text-primary)',
              backgroundColor: isMenuOpen ? 'var(--color-border)' : 'transparent',
              boxShadow: isMenuOpen ? 'var(--shadow-neumorphic-inset)' : 'none'
            }}
          >
            {isMenuOpen ? <X size={20} strokeWidth={2} /> : <Menu size={20} strokeWidth={2} />}
          </button>
        </div>

        {/* Mobile Dropdown Nav Menu */}
        {isMenuOpen && (
          <div className="md:hidden px-4 sm:px-6 pb-6 pt-3 flex flex-col gap-3" style={{ borderTop: '1px solid var(--color-border)', backgroundColor: 'var(--color-surface)' }}>
            <a href="#features" onClick={() => setIsMenuOpen(false)} className="nav-item">
              Features
            </a>
            <a href="#architecture" onClick={() => setIsMenuOpen(false)} className="nav-item">
              Architecture
            </a>
            <a href="#security" onClick={() => setIsMenuOpen(false)} className="nav-item">
              Security
            </a>
            <a href="#api" onClick={() => setIsMenuOpen(false)} className="nav-item">
              API
            </a>
            
            {/* Theme Toggle - Mobile */}
            <button
              onClick={toggleTheme}
              className="btn-secondary w-full flex items-center justify-center gap-2"
              aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
            >
              {theme === 'light' ? (
                <Sun className="w-4 h-4" />
              ) : (
                <Moon className="w-4 h-4" />
              )}
              {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
            </button>
            
            <Link
              to="/login"
              onClick={() => setIsMenuOpen(false)}
              className="w-full text-center text-white"
              style={{
                background: 'linear-gradient(135deg, var(--color-primary), var(--color-primary-hover))',
                padding: '0.75rem 1rem',
                borderRadius: '10px',
                textDecoration: 'none',
                fontWeight: 600,
                fontSize: '0.9375rem',
                boxShadow: 'var(--shadow-neumorphic-sm)'
              }}
            >
              Try Live Demo →
            </Link>
          </div>
        )}
      </header>

      {/* 2. HERO SECTION */}
      <section className="container mx-auto px-5 sm:px-6 pt-12 pb-16 md:py-24 text-center max-w-7xl" style={{ width: '100%', boxSizing: 'border-box' }}>
        <div className="max-w-4xl mx-auto w-full flex flex-col items-center">
          {/* Eyebrow Badge */}
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              backgroundColor: 'var(--color-surface)',
              border: '1px solid var(--color-border)',
              borderRadius: '9999px',
              padding: '0.5rem 1rem',
              marginBottom: '1.5rem',
              maxWidth: '100%',
              flexWrap: 'wrap',
              justifyContent: 'center',
              boxSizing: 'border-box'
            }}
          >
            <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-primary)', lineHeight: 1.2 }}>
              v1.0.0 · AI-Powered · Multi-Provider Cascade
            </span>
          </div>

          {/* Headline */}
          <h1
            style={{
              fontSize: 'clamp(34px, 9vw, 56px)',
              fontWeight: 850,
              lineHeight: 1.1,
              color: 'var(--color-text-primary)',
              letterSpacing: '-0.02em',
              marginBottom: '1rem',
              maxWidth: '100%',
              overflowWrap: 'break-word'
            }}
          >
            Your Inbox, Guarded by AI.
          </h1>

          {/* Subhead */}
          <p
            style={{
              fontSize: 'clamp(15px, 4vw, 17px)',
              lineHeight: 1.6,
              color: 'var(--color-text-secondary)',
              maxWidth: '44rem',
              marginInline: 'auto',
              marginBottom: '2.5rem',
              overflowWrap: 'break-word'
            }}
          >
            Smart labeling, phishing detection, and one-click email rewriting — powered by a self-healing AI cascade (Groq → Gemini → Cohere) built for high availability.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 w-full mb-8">
            <Link
              to="/login"
              style={{
                backgroundColor: 'var(--color-surface)',
                color: 'var(--color-primary)',
                border: '1px solid var(--color-primary)',
                padding: '0.875rem 2rem',
                borderRadius: '10px',
                textDecoration: 'none',
                fontWeight: 700,
                fontSize: '1.0625rem',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                width: '100%',
                maxWidth: '280px',
                whiteSpace: 'nowrap',
                boxShadow: 'var(--shadow-neumorphic-sm)',
                                transition: 'transform var(--transition-fast)',
                                WebkitTapHighlightColor: 'transparent',
                              }}
                              onMouseEnter={(e) => e.target.style.transform = 'translateY(-1px)'}
                              onMouseLeave={(e) => e.target.style.transform = 'none'}
                              css={{
                                '@media (hover: none)': {
                                  '&:active': {
                                    transform: 'translateY(-1px) scale(0.98)',
                                  },
                                },
                              }}
                            >
                              Launch Live App →
            </Link>
            </div>

          {/* Trust Row */}
          <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', fontWeight: 500, marginBottom: '4rem' }}>
            Self-hosted option available — or use our hosted cloud version · MIT Licensed
          </div>

          {/* Dashboard Screenshot Mockup Visual Container */}
          <div className="relative w-full max-w-4xl rounded-2xl border border-slate-700/80 p-1 md:p-3 overflow-visible"
               aria-hidden="true"
               role="presentation"
               style={{ 
                 background: '#0F1729', 
                 boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)',
                 minHeight: '260px'
               }}>
            {/* Glow Behind Mockup wrapper */}
            <div className="mockup-glow" style={{ top: '10%', left: '20%', width: '60%', height: '60%', zIndex: 1 }}></div>

            {/* Dashboard contents */}
            <div className="relative z-10 w-full min-h-60 rounded-xl overflow-hidden text-left flex flex-col md:flex-row gap-4 p-4 border border-slate-800"
                 style={{ backgroundColor: '#131926' }}>
              
              {/* Sidebar segment */}
              <div className="hidden md:flex flex-col gap-2 w-48 border-r border-slate-800/80 pr-4">
                <div className="h-6 bg-slate-800 rounded w-28 mb-3"></div>
                <div className="h-8 bg-slate-800/60 rounded flex items-center px-2 text-indigo-400 text-xs font-semibold">📥 Inbox</div>
                <div className="h-8 bg-transparent rounded flex items-center px-2 text-slate-400 text-xs font-medium">⚠️ Scam Alerts</div>
                <div className="h-8 bg-transparent rounded flex items-center px-2 text-slate-400 text-xs font-medium">🔒 Quarantine</div>
              </div>

              {/* Main Content Mock List area */}
              <div className="flex-1 flex flex-col gap-3 min-w-0">
                <div className="flex justify-between items-center pb-2 border-b border-slate-800">
                  <div className="h-6 bg-slate-800 rounded w-24"></div>
                  <div className="h-6 bg-slate-850 rounded w-32 border border-slate-800"></div>
                </div>

                {/* Email Row 1 */}
                <div className="p-3 bg-slate-800/30 rounded-lg flex items-center justify-between gap-4 border border-slate-800/60">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-white text-xs font-bold truncate">Account Services</span>
                      <span className="text-[10px] text-red-400 bg-red-950/40 px-2 py-0.5 rounded-full border border-red-900/60 font-bold whitespace-nowrap">High Risk 85%</span>
                    </div>
                    <div className="text-slate-400 text-xs truncate mt-1">Suspicious Login Attempt — We spotted login activity from Russia...</div>
                  </div>
                  <div className="text-slate-500 text-[10px] whitespace-nowrap flex-shrink-0">9h ago</div>
                </div>

                {/* Email Row 2 */}
                <div className="p-3 bg-slate-800/30 rounded-lg flex items-center justify-between gap-4 border border-slate-800/60">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-white text-xs font-bold truncate">Spotify Premium</span>
                      <span className="text-[10px] text-green-400 bg-green-950/40 px-2 py-0.5 rounded-full border border-green-900/60 font-bold whitespace-nowrap">Safe 0%</span>
                    </div>
                    <div className="text-slate-400 text-xs truncate mt-1">Spotify Receipt: Invoice #8410294 — Thank you for your payment...</div>
                  </div>
                  <div className="text-slate-500 text-[10px] whitespace-nowrap flex-shrink-0">1d ago</div>
                </div>

                {/* Email Row 3 */}
                <div className="p-3 bg-slate-800/30 rounded-lg flex items-center justify-between gap-4 border border-slate-800/60">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-white text-xs font-bold truncate">SHEIN Global</span>
                      <span className="text-[10px] text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded-full border border-amber-900/60 font-bold whitespace-nowrap">Promo 5%</span>
                    </div>
                    <div className="text-slate-400 text-xs truncate mt-1">Huge Fashion Clearance: Up to 70% Off Today — Don't miss out...</div>
                  </div>
                  <div className="text-slate-500 text-[10px] whitespace-nowrap flex-shrink-0">2d ago</div>
                </div>

              </div>

            </div>
          </div>

        </div>
      </section>

      {/* 3. STATS STRIP */}
      <section className="bg-[var(--color-background)] border-t border-b" style={{ borderColor: 'var(--color-border)', width: '100%', maxWidth: '100%' }}>
        <div className="container mx-auto px-4 sm:px-6 py-8 max-w-7xl">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6 md:gap-8 justify-items-center">
            {stats.map((stat, index) => (
              <div 
                key={index} 
                className="text-center min-w-0 bg-[var(--color-surface)] rounded-[999px] py-3.5 px-6 border border-[var(--color-border)] flex flex-col items-center justify-center w-full"
                style={{ 
                  boxShadow: 'var(--shadow-neumorphic-sm)',
                  maxWidth: '220px'
                }}
              >
                <div
                  style={{
                    fontSize: 'clamp(1.5rem, 4vw, 2.25rem)',
                    fontWeight: 800,
                    color: 'var(--color-primary)',
                    marginBottom: '0.125rem',
                    lineHeight: 1.15
                  }}
                >
                  {stat.value}
                </div>
                <div
                  style={{
                    fontSize: '0.75rem',
                    color: 'var(--color-text-secondary)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    whiteSpace: 'nowrap'
                  }}
                >
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 4. FEATURES SECTION */}
      <section id="features" className="container mx-auto px-4 sm:px-6 py-16 md:py-24 max-w-7xl" style={{ width: '100%', boxSizing: 'border-box' }}>
        <div className="text-center mb-12">
          <h2
            style={{
              fontSize: 'clamp(1.75rem, 5vw, 2.25rem)',
              fontWeight: 800,
              color: 'var(--color-text-primary)',
              marginBottom: '1rem',
              letterSpacing: '-0.015em'
            }}
          >
Everything Your Inbox Needs
          </h2>
          <p style={{ fontSize: '1rem', color: 'var(--color-text-secondary)', maxWidth: '36rem', margin: '0 auto' }}>
            One dashboard. Full AI-powered protection and control.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => {
            const IconComponent = feature.icon;
            return (
              <div key={index} className="feature-card">
                <div
                  className="feature-icon-container"
                  style={{
                    width: '3.25rem',
                    height: '3.25rem',
                    borderRadius: '0.75rem',
                    backgroundColor: `var(${feature.color})`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: '1.25rem',
                    flexShrink: 0,
                    transition: 'transform var(--transition-base)'
                  }}
                >
                  <IconComponent
                    size={22}
                    strokeWidth={1.8}
                    style={{ color: 'var(--color-text-primary)' }}
                  />
                </div>
                <h3
                  style={{
                    fontSize: '1.125rem',
                    fontWeight: 700,
                    color: 'var(--color-text-primary)',
                    marginBottom: '0.75rem'
                  }}
                >
                  {feature.title}
                </h3>
                <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.875rem', lineHeight: 1.6, margin: 0 }}>
                  {feature.description}
                </p>
              </div>
            );
          })}
        </div>
      </section>

      {/* 5. AI CASCADE / PROVIDER STATUS SECTION */}
      <section id="api" className="bg-[var(--color-background)] border-t border-b" style={{ borderColor: 'var(--color-border)', width: '100%', maxWidth: '100%' }}>
        <div className="container mx-auto px-4 sm:px-6 py-16 md:py-24 max-w-4xl" style={{ boxSizing: 'border-box' }}>
          <div className="text-center mb-12">
            <h2
              style={{
                fontSize: 'clamp(1.75rem, 5vw, 2.25rem)',
                fontWeight: 800,
                color: 'var(--color-text-primary)',
                marginBottom: '1rem',
                letterSpacing: '-0.015em'
              }}
            >
              Built for High Availability — AI Cascade
            </h2>
            <p style={{ fontSize: '1rem', color: 'var(--color-text-secondary)', maxWidth: '36rem', margin: '0 auto' }}>
              Automatic failover keeps analysis running even when a provider hits its limit.
            </p>
          </div>

          {/* Vertical Status Stack */}
          <div className="flex flex-col gap-4 mb-8">
            {providers.map((p, index) => {
              const bgPill = p.pulse ? 'var(--color-success-bg)' : 'var(--color-background)';
              const textPill = p.pulse ? 'var(--color-success)' : 'var(--color-text-secondary)';
              const borderPill = p.pulse ? 'rgba(39,174,114,0.2)' : 'var(--color-border)';
              return (
                <div
                  key={index}
                  className="neu-card p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border border-[var(--color-border)]"
                  style={{ backgroundColor: 'var(--color-surface)' }}
                >
                  <div className="flex items-center gap-3">
                    {/* Status Dot */}
                    <div 
                      className={`w-3.5 h-3.5 rounded-full flex-shrink-0 ${p.pulse ? 'pulsing-dot' : ''}`}
                      style={{ 
                        backgroundColor: `var(${p.color})`
                      }} 
                    />
                    <div className="min-w-0">
                      <div style={{ fontSize: '1.0625rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                        {p.name}
                      </div>
                      <div style={{ fontSize: '0.8125rem', color: 'var(--color-text-secondary)', marginTop: '0.125rem' }}>
                        {p.desc}
                      </div>
                    </div>
                  </div>

                  <span
                    className="text-xs font-semibold px-3 py-1 rounded-full border text-center self-start sm:self-center"
                    style={{
                      background: bgPill,
                      color: textPill,
                      borderColor: borderPill
                    }}
                  >
                    {p.status}
                  </span>
                </div>
              );
            })}
          </div>

          <div className="text-center text-sm" style={{ color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
            Flow: <span className="font-semibold" style={{ color: 'var(--color-primary)' }}>Groq (Primary)</span> → <span className="font-semibold" style={{ color: 'var(--color-success)' }}>Gemini (Secondary)</span> → <span className="font-semibold" style={{ color: 'var(--color-warning)' }}>Cohere (Tertiary)</span> → auto-switch on rate limit / failure, zero downtime.
          </div>
        </div>
      </section>

      {/* 6. ARCHITECTURE / HOW IT WORKS SECTION */}
      <section id="architecture" className="container mx-auto px-4 sm:px-6 py-16 md:py-24 max-w-7xl" style={{ width: '100%', boxSizing: 'border-box' }}>
        <div className="max-w-4xl mx-auto w-full">
          <div className="text-center mb-12">
            <h2 style={{ fontSize: 'clamp(1.75rem, 5vw, 2.25rem)', fontWeight: 800, color: 'var(--color-text-primary)', letterSpacing: '-0.015em' }}>
              Built for Speed & Reliability
            </h2>
          </div>

          {/* Timeline / flow diagram */}
          <div className="flex flex-col gap-6 md:gap-8 mb-16">
            {steps.map((step, idx) => (
              <div 
                key={idx} 
                className="flex flex-col sm:flex-row items-start gap-4 p-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-sm relative overflow-hidden"
              >
                <div
                  className="flex-shrink-0 w-24 text-indigo-400 font-bold text-xs uppercase pt-1 tracking-wider"
                  style={{ color: 'var(--color-primary)' }}
                >
                  {step.num}
                </div>
                <div className="flex-1 min-w-0">
                  <h4 style={{ fontSize: '1.0625rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '0.25rem' }}>
                    {step.title}
                  </h4>
                  <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.875rem', lineHeight: 1.5, margin: 0 }}>
                    {step.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Stack Breakdown */}
          <div className="neu-card p-6 md:p-8" style={{ border: '1px solid var(--color-border)' }}>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--color-text-primary)', marginBottom: '1.5rem' }}>
              Stack Breakdown
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-sm">
              <div style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
                <span className="font-semibold block" style={{ color: 'var(--color-primary)', marginBottom: '0.25rem' }}>Frontend</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>React + Vite (port 5173)</span>
              </div>
              <div style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
                <span className="font-semibold block" style={{ color: 'var(--color-primary)', marginBottom: '0.25rem' }}>Backend</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>Python FastAPI (port 8000), 18 REST endpoints</span>
              </div>
              <div style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
                <span className="font-semibold block" style={{ color: 'var(--color-primary)', marginBottom: '0.25rem' }}>Database</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>SQLite3 — analyzed emails + URL cache</span>
              </div>
              <div style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
                <span className="font-semibold block" style={{ color: 'var(--color-primary)', marginBottom: '0.25rem' }}>Desktop</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>Electron wrapper (contextIsolation: true, nodeIntegration: false)</span>
              </div>
              <div style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
                <span className="font-semibold block" style={{ color: 'var(--color-primary)', marginBottom: '0.25rem' }}>Auth</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>Google OAuth 2.0, token auto-refresh</span>
              </div>
              <div style={{ borderBottom: '1px solid var(--color-border)', paddingBottom: '0.75rem' }}>
                <span className="font-semibold block" style={{ color: 'var(--color-primary)', marginBottom: '0.25rem' }}>AI Cascade</span>
                <span style={{ color: 'var(--color-text-secondary)' }}>Groq LLaMA 3 (Primary) → Gemini Flash (Secondary) → Cohere Command-R (Tertiary) · NVIDIA (Reserved)</span>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* 7. SECURITY SECTION */}
      <section id="security" className="bg-[var(--color-background)] border-t border-b" style={{ borderColor: 'var(--color-border)', width: '100%', maxWidth: '100%' }}>
        <div className="container mx-auto px-4 sm:px-6 py-16 md:py-24 max-w-4xl" style={{ boxSizing: 'border-box' }}>
          <div className="text-center mb-12">
            <div className="mb-4 inline-block shield-animated">
              <Shield size={48} style={{ color: 'var(--color-success)' }} strokeWidth={1.8} />
            </div>
            <h2
              style={{
                fontSize: 'clamp(1.75rem, 5vw, 2.25rem)',
                fontWeight: 800,
                color: 'var(--color-text-primary)',
                letterSpacing: '-0.015em'
              }}
            >
              Privacy-First by Design
            </h2>
          </div>

          <div className="flex flex-col gap-4 max-w-2xl mx-auto">
            {securityChecklist.map((item, index) => (
              <div
                key={index}
                className="neu-card p-4 flex items-start gap-3 border border-[var(--color-border)]"
                style={{ backgroundColor: 'var(--color-surface)' }}
              >
                <CheckCircle
                  size={18}
                  style={{ color: 'var(--color-success)', marginTop: '0.125rem', flexShrink: 0 }}
                  strokeWidth={2}
                />
                <span
                  style={{
                    fontSize: '0.9375rem',
                    fontWeight: 500,
                    color: 'var(--color-text-secondary)',
                    lineHeight: 1.5,
                    overflowWrap: 'break-word',
                    minWidth: 0
                  }}
                >
                  {item}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 8. CTA / GET STARTED SECTION */}
      <section className="container mx-auto px-4 sm:px-6 py-16 md:py-24 max-w-5xl" style={{ width: '100%', boxSizing: 'border-box' }}>
        <div
          className="p-8 md:p-14 text-center"
          style={{
            backgroundColor: 'var(--color-surface)',
            border: '1px solid var(--color-primary)',
            borderRadius: '1.5rem',
            width: '100%',
            maxWidth: '100%',
            boxSizing: 'border-box',
            boxShadow: 'var(--shadow-lg)'
          }}
        >
          <h2
            style={{
              fontSize: 'clamp(1.8rem, 6vw, 2.75rem)',
              fontWeight: 800,
              color: 'var(--color-text-primary)',
              marginBottom: '1rem',
              lineHeight: 1.2
            }}
          >
            See It in Action
          </h2>
          <p
            style={{
              fontSize: 'clamp(1rem, 3.5vw, 1.1875rem)',
              color: 'var(--color-text-secondary)',
              marginBottom: '2.5rem',
              maxWidth: '38rem',
              marginInline: 'auto',
              lineHeight: 1.6
            }}
          >
            No signup walls — connect your Gmail and see AI triage your inbox in seconds.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 w-full" style={{ boxSizing: 'border-box' }}>
            <Link
              to="/login"
              style={{
                backgroundColor: 'var(--color-primary)',
                color: '#FFFFFF',
                padding: '0.875rem 2rem',
                borderRadius: '10px',
                textDecoration: 'none',
                fontWeight: 700,
                fontSize: '1.0625rem',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                width: '100%',
                maxWidth: '280px',
                whiteSpace: 'nowrap',
                transition: 'transform var(--transition-fast), background-color var(--transition-fast)'
              }}
              onMouseEnter={(e) => e.target.style.transform = 'scale(1.03)'}
              onMouseLeave={(e) => e.target.style.transform = 'none'}
            >
              Try Live Demo →
            </Link>
            
            <a
              href="#"
              style={{
                backgroundColor: 'var(--color-surface)',
                color: 'var(--color-primary)',
                padding: '0.875rem 2rem',
                borderRadius: '10px',
                textDecoration: 'none',
                fontWeight: 600,
                fontSize: '1.0625rem',
                border: '1px solid var(--color-primary)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '100%',
                maxWidth: '280px',
                whiteSpace: 'nowrap',
                transition: 'transform var(--transition-fast), background-color var(--transition-fast), color var(--transition-fast)'
              }}
              onMouseEnter={(e) => {
                e.target.style.transform = 'scale(1.03)';
                e.target.style.backgroundColor = 'var(--color-primary)';
                e.target.style.color = '#FFFFFF';
              }}
              onMouseLeave={(e) => {
                e.target.style.transform = 'none';
                e.target.style.backgroundColor = 'var(--color-surface)';
                e.target.style.color = 'var(--color-primary)';
              }}
            >
              Read the Docs
            </a>

            </div>
        </div>
      </section>

      {/* 9. FOOTER */}
      <footer
        style={{
          backgroundColor: 'var(--color-surface)',
          borderTop: '1px solid var(--color-border)',
          width: '100%',
          maxWidth: '100%'
        }}
      >
          <div className="container mx-auto px-4 sm:px-6 py-12 max-w-7xl" style={{ width: '100%', maxWidth: '100%' }}>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-8 mb-12">
            {/* Brand */}
            <div className="min-w-0" style={{ width: '100%' }}>
              <div className="flex items-center gap-2 mb-4">
                <Mail size={22} style={{ color: 'var(--color-primary)' }} strokeWidth={1.8} />
                <span
                  style={{
                    fontSize: '1.1875rem',
                    fontWeight: 700,
                    color: 'var(--color-text-primary)'
                  }}
                >
                  Gmail Manager
                </span>
              </div>
              <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.8125rem', lineHeight: 1.6, margin: 0 }}>
                AI-powered email intelligence, built with a multi-model cascade.
              </p>
            </div>

            {/* Product */}
            <div className="min-w-0" style={{ width: '100%' }}>
              <h4
                style={{
                  fontSize: '0.8125rem',
                  fontWeight: 700,
                  color: 'var(--color-text-primary)',
                  marginBottom: '1rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em'
                }}
              >
                Product
              </h4>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                <li style={{ marginBottom: '0.5rem' }}>
                  <a href="#features" style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: '0.8125rem' }} className="hover:text-primary">
                    Features
                  </a>
                </li>
                <li style={{ marginBottom: '0.5rem' }}>
                  <Link to="/login" style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: '0.8125rem' }} className="hover:text-primary">
                    Live Demo
                  </Link>
                </li>
                <li style={{ marginBottom: '0.5rem' }}>
                  <a href="#architecture" style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: '0.8125rem' }} className="hover:text-primary">
                    Architecture
                  </a>
                </li>
              </ul>
            </div>

            {/* Legal */}
            <div className="min-w-0" style={{ width: '100%' }}>
              <h4
                style={{
                  fontSize: '0.8125rem',
                  fontWeight: 700,
                  color: 'var(--color-text-primary)',
                  marginBottom: '1rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em'
                }}
              >
                Legal
              </h4>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                <li style={{ marginBottom: '0.5rem' }}>
                  <Link to="/privacy-policy" style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: '0.8125rem' }}>
                    Privacy Policy
                  </Link>
                </li>
                <li style={{ marginBottom: '0.5rem' }}>
                  <Link to="/terms" style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: '0.8125rem' }}>
                    Terms of Service
                  </Link>
                </li>
                <li style={{ marginBottom: '0.5rem' }}>
                  <Link to="/cookie-policy" style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: '0.8125rem' }}>
                    Cookie Policy
                  </Link>
                </li>
                <li style={{ marginBottom: '0.5rem' }}>
                  <Link to="/refund-policy" style={{ color: 'var(--color-text-secondary)', textDecoration: 'none', fontSize: '0.8125rem' }}>
                    Refund Policy
                  </Link>
                </li>
              </ul>
            </div>
          </div>

          {/* Bottom Bar */}
          <div
            style={{
              paddingTop: '2rem',
              borderTop: '1px solid var(--color-border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '1rem'
            }}
          >
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: 1.6 }}>
              © 2026 Gmail Manager. All rights reserved.<br/>
              Contact: legal@gmailmanager.com
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)', fontWeight: 550 }}>
              Privacy-first architecture with self-hosted and cloud options.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default LandingPage;
