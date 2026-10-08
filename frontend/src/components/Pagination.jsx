/**
 * Pagination.jsx - Reusable pagination component
 */

import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

export default function Pagination({
  currentPage,
  totalPages,
  hasNextPage,
  hasPrevPage,
  onPageChange,
  onFirstPage,
  onLastPage,
  onNextPage,
  onPrevPage,
  totalItems,
  itemsPerPage,
}) {
  // Calculate visible page numbers (show max 5 pages)
  const getPageNumbers = () => {
    const pages = [];
    const maxVisible = 5;
    
    let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);
    
    // Adjust start if we're near the end
    if (endPage - startPage < maxVisible - 1) {
      startPage = Math.max(1, endPage - maxVisible + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
      pages.push(i);
    }
    
    return pages;
  };

  const pageNumbers = getPageNumbers();
  const startItem = (currentPage - 1) * itemsPerPage + 1;
  const endItem = Math.min(currentPage * itemsPerPage, totalItems);

  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-between border-t border-gray-200 bg-white px-4 py-3 sm:px-6">
      {/* Items count */}
      <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
        <div>
          <p className="text-sm text-gray-700">
            Showing <span className="font-medium">{startItem}</span> to{' '}
            <span className="font-medium">{endItem}</span> of{' '}
            <span className="font-medium">{totalItems}</span> results
          </p>
        </div>
      </div>

      {/* Pagination controls */}
      <div className="flex items-center justify-center space-x-2">
        {/* First page button */}
        <button
          onClick={onFirstPage}
          disabled={!hasPrevPage}
          className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="First page"
        >
          <ChevronsLeft className="w-4 h-4" />
        </button>

        {/* Previous button */}
        <button
          onClick={onPrevPage}
          disabled={!hasPrevPage}
          className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Previous page"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {/* Page numbers */}
        <div className="hidden sm:flex space-x-1">
          {pageNumbers.map((pageNum) => (
            <button
              key={pageNum}
              onClick={() => onPageChange(pageNum)}
              className={`inline-flex items-center justify-center min-w-[2rem] h-8 px-3 rounded-md text-sm font-medium transition-colors ${
                pageNum === currentPage
                  ? 'bg-primary-600 text-white'
                  : 'border border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              {pageNum}
            </button>
          ))}
        </div>

        {/* Mobile page indicator */}
        <div className="sm:hidden">
          <span className="text-sm text-gray-700">
            Page {currentPage} of {totalPages}
          </span>
        </div>

        {/* Next button */}
        <button
          onClick={onNextPage}
          disabled={!hasNextPage}
          className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Next page"
        >
          <ChevronRight className="w-4 h-4" />
        </button>

        {/* Last page button */}
        <button
          onClick={onLastPage}
          disabled={!hasNextPage}
          className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Last page"
        >
          <ChevronsRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
