/**
 * Sidebar.jsx — Responsive Navigation Sidebar (Light Design System)
 * Desktop: 240px fixed sidebar
 * Mobile: Slide-out drawer with hamburger menu
 * Uses .nav-item classes from unified design system
 * 
 * Updated: 2026-08-11 - Light design system implementation
 */

import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { apiRequest, clearAuthToken } from '../lib/api';
import { useTheme } from '../context/ThemeContext';

// Navigation items with icons and paths
const NAV_ITEMS = [
  {
    path: '/inbox',
    label: 'Inbox',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859m-17.399 0V6.108c0-1.135.845-2.098 1.976-2.192a48.424 48.424 0 0110.753 0c1.13.094 1.976 1.057 1.976 2.192V13.5" />
      </svg>
    ),
  },
  {
    path: '/scam-alerts',
    label: 'Scam Alerts',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
      </svg>
    ),
  },
  {
    path: '/quarantine',
    label: 'Quarantine',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
      </svg>
    ),
  },
  {
    path: '/rewriter',
    label: 'Email Rewriter',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
      </svg>
    ),
  },
  {
    path: '/settings',
    label: 'Settings',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
];

function Sidebar({ userEmail, mobileMenuOpen = false, onCloseMobileMenu = () => {} }) {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();

  async function handleLogout() {
    try {
      await apiRequest('/auth/logout', {
        method: 'POST',
      });
    } catch (err) { /* proceed anyway */ }
    clearAuthToken();
    navigate('/login');
  }

  // Get initials from email
  const initials = userEmail
    ? userEmail.split('@')[0].slice(0, 2).toUpperCase()
    : 'GM';

  // Sidebar content (shared between desktop and mobile)
  const SidebarContent = () => (
    <>
      {/* App Logo + Name */}
      <div className="p-5 flex items-center gap-3">
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{
            background: 'var(--color-surface)',
            boxShadow: 'var(--shadow-neumorphic-sm)'
          }}
        >
          <svg className="w-5 h-5" style={{ color: 'var(--color-primary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
          </svg>
        </div>
        <div>
          <h1 className="text-sm font-bold leading-tight" style={{ color: 'var(--color-text-primary)' }}>Gmail Manager</h1>
          <p className="text-xs leading-tight" style={{ color: 'var(--color-text-muted)' }}>Intelligence</p>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            onClick={onCloseMobileMenu}
            className={({ isActive }) =>
              `nav-item ${isActive ? 'active' : ''}`
            }
          >
            {item.icon}
            <span className="text-sm font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* User Info + Logout */}
      <div className="p-4" style={{ borderTop: '1px solid var(--color-border)' }}>
        <div className="flex items-center gap-3 mb-3">
          <div
            className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
            style={{
              background: 'var(--color-primary)',
              color: 'var(--color-text-primary)',
              boxShadow: 'var(--shadow-flat-sm)'
            }}
          >
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate" style={{ color: 'var(--color-text-primary)' }}>{userEmail || 'User'}</p>
            <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>Active</p>
          </div>
        </div>
        
        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="btn-secondary w-full flex items-center justify-center gap-2 mb-3"
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        >
          {theme === 'light' ? (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
            </svg>
          )}
          {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
        </button>
        
        <button
          onClick={handleLogout}
          className="btn-secondary w-full flex items-center justify-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75" />
          </svg>
          Logout
        </button>
      </div>
    </>
  );

  return (
    <>
      {/* Desktop Sidebar - always visible on md and above */}
      <div
        className="hidden md:flex fixed left-0 top-0 h-screen flex-col"
        style={{
          width: '240px',
          background: 'var(--color-surface)',
          borderRight: '1px solid var(--color-border)',
          zIndex: 50,
        }}
      >
        <SidebarContent />
      </div>

      {/* Mobile Drawer - slide-in from left on mobile */}
      <div
        className={`
          md:hidden fixed left-0 top-0 h-screen flex flex-col
          transition-transform duration-300 ease-out
          ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
        style={{
          width: '280px',
          background: 'var(--color-surface)',
          borderRight: '1px solid var(--color-border)',
          zIndex: 200,
          paddingTop: 'env(safe-area-inset-top, 0px)',
        }}
      >
        {/* Close button - mobile only */}
        <button
          onClick={onCloseMobileMenu}
          className="absolute top-4 right-4 p-2 rounded-lg transition-colors z-10"
          style={{ 
            background: 'var(--color-surface)',
            color: 'var(--color-text-secondary)',
            boxShadow: '2px 2px 4px rgba(160, 174, 192, 0.15), -2px -2px 4px rgba(255, 255, 255, 0.8)'
          }}
          aria-label="Close menu"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <SidebarContent />
      </div>

      {/* Mobile Overlay */}
      {mobileMenuOpen && (
        <div
          className="md:hidden fixed inset-0"
          style={{ 
            backgroundColor: 'rgba(0, 0, 0, 0.6)',
            zIndex: 199,
            backdropFilter: 'blur(2px)',
          }}
          onClick={onCloseMobileMenu}
        />
      )}
    </>
  );
}

export default Sidebar;
