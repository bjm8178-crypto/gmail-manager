/**
 * AnimatedBackground.jsx — Minimal Background Component
 * Subtle background for light and dark mode design system
 * 
 * Features:
 * - Clean adaptive background (var(--color-background))
 * - Minimal subtle particles (barely visible)
 * - No distracting animations
 * - Performance optimized
 */

import React, { useEffect, useState } from 'react';

function AnimatedBackground() {
  const [particles, setParticles] = useState([]);

  useEffect(() => {
    // Generate 12 subtle particles (reduced from 30)
    const newParticles = Array.from({ length: 12 }, (_, i) => ({
      id: i,
      left: Math.random() * 100,
      top: Math.random() * 100,
      size: Math.random() * 2 + 1,
      duration: Math.random() * 30 + 20,
      delay: Math.random() * 5,
      xMove: Math.random() * 50 - 25,
      yMove: Math.random() * 50 - 25,
    }));
    setParticles(newParticles);
  }, []);

  return (
    <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
      {/* Clean Background */}
      <div
        className="absolute inset-0"
        style={{
          background: 'var(--color-background)',
        }}
      />

      {/* Minimal Floating Particles */}
      {particles.map((particle) => (
        <div
          key={particle.id}
          className="absolute rounded-full"
          style={{
            left: `${particle.left}%`,
            top: `${particle.top}%`,
            width: `${particle.size}px`,
            height: `${particle.size}px`,
            backgroundColor: 'var(--color-border)',
            opacity: 0.08,
            animation: `floatSubtle ${particle.duration}s ease-in-out infinite`,
            animationDelay: `${particle.delay}s`,
            '--x-move': `${particle.xMove}px`,
            '--y-move': `${particle.yMove}px`,
          }}
        />
      ))}

      {/* Subtle Grid Pattern Overlay */}
      <div
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `
            linear-gradient(var(--color-border) 1px, transparent 1px),
            linear-gradient(90deg, var(--color-border) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
        }}
      />

      {/* CSS Animations */}
      <style>{`
        @keyframes floatSubtle {
          0%, 100% {
            transform: translate(0, 0);
          }
          50% {
            transform: translate('var(--x-move)', 'var(--y-move)');
          }
        }
      `}</style>
    </div>
  );
}

export default AnimatedBackground;
