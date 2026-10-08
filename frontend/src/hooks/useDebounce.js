/**
 * useDebounce.js - Debounce hook for input handlers
 * Prevents excessive API calls on rapid user input
 */

import { useState, useEffect } from 'react';

/**
 * Debounce a value - delays updating the value until after a delay
 * @param {any} value - The value to debounce
 * @param {number} delay - Delay in milliseconds (default 500ms)
 * @returns {any} - The debounced value
 */
export function useDebounce(value, delay = 500) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    // Set up the timeout
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    // Clean up on unmount or when value/delay changes
    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Debounce a callback function
 * @param {Function} callback - The function to debounce
 * @param {number} delay - Delay in milliseconds (default 500ms)
 * @returns {Function} - The debounced function
 */
export function useDebouncedCallback(callback, delay = 500) {
  const [timeoutId, setTimeoutId] = useState(null);

  return (...args) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    const newTimeoutId = setTimeout(() => {
      callback(...args);
    }, delay);

    setTimeoutId(newTimeoutId);
  };
}

export default useDebounce;
