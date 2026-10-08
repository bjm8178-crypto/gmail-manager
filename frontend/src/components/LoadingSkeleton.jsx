/**
 * LoadingSkeleton.jsx - Loading skeleton components for better perceived performance
 */

export function EmailCardSkeleton() {
  return (
    <div className="animate-pulse bg-white rounded-lg shadow-sm p-4 mb-3">
      <div className="flex items-start space-x-3">
        {/* Avatar skeleton */}
        <div className="w-10 h-10 rounded-full bg-gray-200"></div>
        
        <div className="flex-1 space-y-2">
          {/* Sender name */}
          <div className="h-4 bg-gray-200 rounded w-1/4"></div>
          
          {/* Subject */}
          <div className="h-4 bg-gray-200 rounded w-3/4"></div>
          
          {/* Snippet */}
          <div className="h-3 bg-gray-100 rounded w-full"></div>
          <div className="h-3 bg-gray-100 rounded w-2/3"></div>
        </div>
        
        {/* Badge skeleton */}
        <div className="h-6 w-20 bg-gray-200 rounded-full"></div>
      </div>
    </div>
  );
}

export function EmailListSkeleton({ count = 5 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <EmailCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function StatsCardSkeleton() {
  return (
    <div className="animate-pulse bg-white rounded-lg shadow-sm p-6">
      <div className="space-y-3">
        <div className="h-6 bg-gray-200 rounded w-1/3"></div>
        <div className="h-10 bg-gray-200 rounded w-1/2"></div>
        <div className="h-4 bg-gray-100 rounded w-2/3"></div>
      </div>
    </div>
  );
}

export function LabelBadgeSkeleton() {
  return (
    <div className="animate-pulse inline-block">
      <div className="h-6 w-24 bg-gray-200 rounded-full"></div>
    </div>
  );
}

export function ButtonSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-10 w-32 bg-gray-200 rounded-lg"></div>
    </div>
  );
}

export default {
  EmailCardSkeleton,
  EmailListSkeleton,
  StatsCardSkeleton,
  LabelBadgeSkeleton,
  ButtonSkeleton,
};
