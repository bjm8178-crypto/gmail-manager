import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite configuration for Gmail Manager frontend
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,       // Dev server port — Electron points here
    strictPort: true,  // Fail if port is already in use
  },
  build: {
    outDir: 'dist',    // Production build output directory
    
    // Performance optimizations
    target: 'es2015',
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,  // Remove console.log in production
        drop_debugger: true,
      },
    },
    
    // Code splitting and chunk optimization
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor chunk for React and core libraries
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          // Separate chunk for icons
          'vendor-icons': ['lucide-react'],
          // Separate chunk for utilities
          'vendor-utils': ['react-hot-toast'],
        },
        // Optimize chunk file names
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]',
      },
    },
    
    // Chunk size warnings
    chunkSizeWarningLimit: 1000,
    
    // Source maps for debugging (disable in production for smaller builds)
    sourcemap: false,
  },
  
  // Dependency optimization
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom', 'lucide-react'],
  },
});
