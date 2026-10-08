/**
 * usePagination.js - Pagination hook for large lists
 */

import { useState, useMemo } from 'react';

/**
 * Pagination hook for client-side pagination
 * @param {Array} data - The full dataset to paginate
 * @param {number} itemsPerPage - Items per page (default 20)
 * @returns {Object} - Pagination state and controls
 */
export function usePagination(data = [], itemsPerPage = 20) {
  const [currentPage, setCurrentPage] = useState(1);

  // Calculate total pages
  const totalPages = Math.ceil(data.length / itemsPerPage);

  // Get current page data
  const currentData = useMemo(() => {
    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    return data.slice(startIndex, endIndex);
  }, [data, currentPage, itemsPerPage]);

  // Navigation functions
  const goToPage = (page) => {
    const pageNumber = Math.max(1, Math.min(page, totalPages));
    setCurrentPage(pageNumber);
  };

  const nextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  const prevPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  const goToFirstPage = () => {
    setCurrentPage(1);
  };

  const goToLastPage = () => {
    setCurrentPage(totalPages);
  };

  // Reset to first page when data changes
  const resetPagination = () => {
    setCurrentPage(1);
  };

  return {
    currentData,
    currentPage,
    totalPages,
    totalItems: data.length,
    itemsPerPage,
    hasNextPage: currentPage < totalPages,
    hasPrevPage: currentPage > 1,
    goToPage,
    nextPage,
    prevPage,
    goToFirstPage,
    goToLastPage,
    resetPagination,
  };
}

export default usePagination;
