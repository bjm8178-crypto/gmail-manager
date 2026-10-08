/**
 * main.jsx — React Entry Point
 * Mounts the root React component into the DOM.
 * Sets up React Router for client-side navigation.
 * Wraps app in AnalysisProvider for persistent analysis state.
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AnalysisProvider } from './context/AnalysisContext';
import './index.css';

// Mount the React app into the #root div in index.html
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <AnalysisProvider>
        <App />
      </AnalysisProvider>
    </BrowserRouter>
  </React.StrictMode>
);
