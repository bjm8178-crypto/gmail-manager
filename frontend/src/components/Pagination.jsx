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
    <div 
      className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-3 rounded-xl border mt-6"
      style={{
        backgroundColor: 'var(--color-surface)',
        borderColor: 'var(--color-border)',
      }}
    >
      {/* Items count */}
      <div className="flex items-center text-xs sm:text-sm" style={{ color: 'var(--color-text-secondary)' }}>
        <span>
          Showing <strong style={{ color: 'var(--color-text-primary)' }}>{startItem}</strong>-
          <strong style={{ color: 'var(--color-text-primary)' }}>{endItem}</strong> of{' '}
          <strong style={{ color: 'var(--color-text-primary)' }}>{totalItems}</strong> emails
        </span>
      </div>

      {/* Pagination controls */}
      <div className="flex items-center space-x-1.5">
        {/* First page button */}
        <button
          onClick={onFirstPage}
          disabled={!hasPrevPage}
          style={{
            borderColor: 'var(--color-border)',
            backgroundColor: 'var(--color-surface)',
            color: 'var(--color-text-primary)',
          }}
          className="hidden sm:inline-flex items-center justify-center w-8 h-8 rounded-lg border text-sm font-medium transition-all hover:opacity-80 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed"
          aria-label="First page"
          title="First page"
        >
          <ChevronsLeft className="w-4 h-4" />
        </button>

        {/* Previous button (<) */}
        <button
          onClick={onPrevPage}
          disabled={!hasPrevPage}
          style={{
            borderColor: 'var(--color-border)',
            backgroundColor: 'var(--color-surface)',
            color: 'var(--color-text-primary)',
          }}
          className="inline-flex items-center justify-center w-8 h-8 rounded-lg border text-sm font-medium transition-all hover:opacity-80 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed"
          aria-label="Previous page"
          title="Previous page"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {/* Page numbers */}
        <div className="hidden sm:flex items-center space-x-1">
          {pageNumbers.map((pageNum) => (
            <button
              key={pageNum}
              onClick={() => onPageChange(pageNum)}
              style={
                pageNum === currentPage
                  ? {
                      backgroundColor: 'var(--color-primary)',
                      color: '#ffffff',
                      borderColor: 'var(--color-primary)',
                    }
                  : {
                      backgroundColor: 'var(--color-surface)',
                      color: 'var(--color-text-secondary)',
                      borderColor: 'var(--color-border)',
                    }
              }
              className="inline-flex items-center justify-center min-w-[2rem] h-8 px-2.5 rounded-lg border text-xs font-semibold transition-all hover:opacity-90 active:scale-95"
            >
              {pageNum}
            </button>
          ))}
        </div>

        {/* Mobile page indicator */}
        <div className="sm:hidden px-2">
          <span className="text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>
            Page {currentPage} of {totalPages}
          </span>
        </div>

        {/* Next button (>) */}
        <button
          onClick={onNextPage}
          disabled={!hasNextPage}
          style={{
            borderColor: 'var(--color-border)',
            backgroundColor: 'var(--color-surface)',
            color: 'var(--color-text-primary)',
          }}
          className="inline-flex items-center justify-center w-8 h-8 rounded-lg border text-sm font-medium transition-all hover:opacity-80 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed"
          aria-label="Next page"
          title="Next page"
        >
          <ChevronRight className="w-4 h-4" />
        </button>

        {/* Last page button */}
        <button
          onClick={onLastPage}
          disabled={!hasNextPage}
          style={{
            borderColor: 'var(--color-border)',
            backgroundColor: 'var(--color-surface)',
            color: 'var(--color-text-primary)',
          }}
          className="hidden sm:inline-flex items-center justify-center w-8 h-8 rounded-lg border text-sm font-medium transition-all hover:opacity-80 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed"
          aria-label="Last page"
          title="Last page"
        >
          <ChevronsRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
