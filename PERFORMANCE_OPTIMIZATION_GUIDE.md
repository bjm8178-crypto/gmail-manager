# Performance Optimization Implementation Guide

## ✅ Completed Optimizations

### Backend Optimizations

#### 1. **API Response Caching** ✓
- **File:** `backend/cache_manager.py`
- **Features:**
  - Thread-safe LRU cache with TTL
  - Separate caches for API responses, DB queries, and ML results
  - Cache statistics tracking (hit rate, size)
  - User-specific cache invalidation
- **Configuration:**
  - API cache: 1000 items, 5min TTL
  - Query cache: 500 items, 3min TTL
  - ML cache: 200 items, 1hr TTL

#### 2. **Response Compression** ✓
- **File:** `backend/compression.py`
- **Features:**
  - GZip compression middleware
  - Automatic compression for responses > 1KB
  - Skips already compressed formats (images, videos)
  - Level 6 compression (balance of speed/size)
- **Expected savings:** 60-80% for JSON responses

#### 3. **Database Indexing** ✓
- **Files:** 
  - `backend/db_indices.sql` - Index definitions
  - `backend/apply_indices.py` - Index application script
- **Indices added:**
  - `analyzed_emails`: user_id, status, scam_score, sender, label_id
  - `analyzed_emails_pending_sync`: Composite index for sync queries
  - `custom_labels`: user_id, label_name
  - `url_cache`: email_id, url, checked_at
  - `retry_queue`: user_id, next_retry, status
- **Expected improvement:** 10-100x faster on filtered queries

#### 4. **Connection Pooling** ✓
- **File:** `backend/database.py` (already implemented)
- **Configuration:** 2-50 connections (ThreadedConnectionPool)
- **Status:** Already active in your codebase

### Frontend Optimizations

#### 5. **Frontend API Caching** ✓
- **File:** `frontend/src/lib/apiCache.js`
- **Features:**
  - LRU cache with TTL
  - Automatic cache invalidation on mutations
  - Per-endpoint cache configuration
  - Cache statistics
- **Configuration:**
  - `/emails`: 30s TTL
  - `/labels`: 5min TTL
  - `/settings`: 5min TTL

#### 6. **Code Splitting & Minification** ✓
- **File:** `frontend/vite.config.js`
- **Optimizations:**
  - Manual chunking (vendor-react, vendor-icons, vendor-utils)
  - Terser minification with console.log removal
  - Optimized chunk file names
  - Disabled source maps in production
- **Expected savings:** 30-40% smaller bundle size

#### 7. **Loading Skeletons** ✓
- **File:** `frontend/src/components/LoadingSkeleton.jsx`
- **Components:**
  - EmailCardSkeleton
  - EmailListSkeleton
  - StatsCardSkeleton
  - LabelBadgeSkeleton
  - ButtonSkeleton
- **Benefit:** Better perceived performance

#### 8. **Pagination** ✓
- **Files:**
  - `frontend/src/components/Pagination.jsx`
  - `frontend/src/hooks/usePagination.js`
- **Features:**
  - Client-side pagination hook
  - Pagination UI component
  - Configurable items per page
- **Default:** 20 items per page

#### 9. **Debounced Input** ✓
- **File:** `frontend/src/hooks/useDebounce.js`
- **Hooks:**
  - `useDebounce(value, delay)` - Debounce values
  - `useDebouncedCallback(callback, delay)` - Debounce functions
- **Default delay:** 500ms

---

## 🚀 Deployment Steps

### Step 1: Install New Dependencies

```bash
# Backend
cd backend
pip install redis==5.0.1 hiredis==2.3.2

# Frontend (no new dependencies needed)
```

### Step 2: Apply Database Indices

**Option A - Automatic (on next deployment):**
Indices will be applied automatically on server startup.

**Option B - Manual (run now):**
```bash
cd backend
python apply_indices.py
```

### Step 3: Update Environment Variables (Optional)

Add to Railway environment variables (optional - for future Redis upgrade):
```
REDIS_URL=redis://localhost:6379  # If using Redis in future
```

### Step 4: Deploy

```bash
# Commit and push to trigger auto-deployment
git add .
git commit -m "feat: comprehensive performance optimizations

- Add API response caching (5min TTL)
- Add GZip compression middleware
- Add database indices for all major queries
- Add frontend caching layer
- Add code splitting and minification
- Add loading skeletons and pagination
- Add debounced input handlers"

git push origin main
```

Vercel and Railway will auto-deploy.

---

## 📊 Performance Monitoring

### Check Cache Performance

Visit: `https://your-railway-app.railway.app/health`

Returns:
```json
{
  "status": "healthy",
  "cache_stats": {
    "api_cache": {
      "size": 45,
      "hits": 1234,
      "misses": 567,
      "hit_rate": "68.5%"
    },
    "query_cache": { ... },
    "ml_cache": { ... }
  }
}
```

### Frontend Cache Stats

In browser console:
```javascript
import { apiCache } from './lib/apiCache';
console.log(apiCache.getStats());
```

---

## 🎯 Usage Examples

### Backend: Using Cache Decorators

```python
from cache_manager import cache_api_response, cache_query_result

# Cache API endpoint
@cache_api_response(ttl=300, key_prefix="emails")
async def get_emails(user_id: int):
    # Expensive operation
    return emails

# Cache database query
@cache_query_result(ttl=180, key_prefix="labels")
def get_labels(user_id: int):
    # Database query
    return labels
```

### Frontend: Using Pagination

```jsx
import { usePagination } from '../hooks/usePagination';
import Pagination from '../components/Pagination';
import { EmailListSkeleton } from '../components/LoadingSkeleton';

function EmailList({ emails, loading }) {
  const {
    currentData,
    currentPage,
    totalPages,
    hasNextPage,
    hasPrevPage,
    goToPage,
    nextPage,
    prevPage,
    goToFirstPage,
    goToLastPage,
    totalItems,
    itemsPerPage,
  } = usePagination(emails, 20);

  if (loading) return <EmailListSkeleton count={10} />;

  return (
    <>
      {currentData.map(email => <EmailCard key={email.id} {...email} />)}
      
      <Pagination
        currentPage={currentPage}
        totalPages={totalPages}
        hasNextPage={hasNextPage}
        hasPrevPage={hasPrevPage}
        onPageChange={goToPage}
        onNextPage={nextPage}
        onPrevPage={prevPage}
        onFirstPage={goToFirstPage}
        onLastPage={goToLastPage}
        totalItems={totalItems}
        itemsPerPage={itemsPerPage}
      />
    </>
  );
}
```

### Frontend: Using Debounce

```jsx
import { useDebounce, useDebouncedCallback } from '../hooks/useDebounce';

function SearchBox() {
  const [searchTerm, setSearchTerm] = useState('');
  const debouncedSearch = useDebounce(searchTerm, 500);

  useEffect(() => {
    if (debouncedSearch) {
      // API call only fires after 500ms of no typing
      searchEmails(debouncedSearch);
    }
  }, [debouncedSearch]);

  return (
    <input
      value={searchTerm}
      onChange={(e) => setSearchTerm(e.target.value)}
      placeholder="Search emails..."
    />
  );
}
```

---

## 🔍 Testing Performance

### 1. **Check Compression**
```bash
curl -H "Accept-Encoding: gzip" -I https://your-app.railway.app/emails
# Look for: Content-Encoding: gzip
```

### 2. **Check Response Times**
```bash
# Before optimization baseline
time curl https://your-app.railway.app/emails

# After optimization (should be faster on repeated calls)
time curl https://your-app.railway.app/emails
```

### 3. **Run Lighthouse Audit**
```bash
cd frontend
npm run build
npm run preview
# Open Chrome DevTools > Lighthouse > Run Audit
```

### 4. **Check Bundle Size**
```bash
cd frontend
npm run build
# Check dist/ folder size
du -sh dist/
```

---

## 🎛️ Fine-Tuning

### Adjust Cache TTLs

**Backend** (`cache_manager.py`):
```python
api_cache = LRUCache(max_size=1000, default_ttl=300)  # Increase/decrease TTL
```

**Frontend** (`apiCache.js`):
```javascript
export const CACHE_CONFIG = {
  '/emails': { ttl: 30000 },  // Adjust per endpoint
};
```

### Adjust Pagination Size

```jsx
const { currentData } = usePagination(data, 50);  // Change 20 to 50
```

### Adjust Debounce Delay

```javascript
const debouncedSearch = useDebounce(searchTerm, 300);  // Faster response
```

---

## 📈 Expected Performance Gains

| Optimization | Expected Improvement |
|--------------|---------------------|
| API Caching | 50-90% faster repeated requests |
| GZip Compression | 60-80% smaller payloads |
| Database Indices | 10-100x faster queries |
| Code Splitting | 30-40% smaller initial load |
| Pagination | Instant rendering of large lists |
| Debounce | 80-95% fewer API calls |
| Loading Skeletons | Better perceived performance |

---

## ⚠️ Important Notes

1. **Cache Invalidation:** Cache is automatically cleared on logout and on mutations (POST/PUT/DELETE)
2. **Memory Usage:** LRU cache evicts oldest entries when full - monitor with `/health` endpoint
3. **Database Indices:** Applied automatically on startup - no manual intervention needed
4. **Redis Optional:** Current implementation uses in-memory cache - can upgrade to Redis for multi-instance deployments

---

## 🐛 Troubleshooting

### Issue: Cache not working
**Solution:** Check browser console for cache hit logs: `[API CACHE HIT] /emails`

### Issue: Indices not applied
**Solution:** 
```bash
cd backend
python apply_indices.py
# Check logs for "✓ All indices applied successfully"
```

### Issue: Bundle too large
**Solution:** Check `vite.config.js` manualChunks - add more vendor splits

---

## 🔄 Next Steps (Future Enhancements)

- [ ] Upgrade to Redis for distributed caching (multi-instance support)
- [ ] Add service worker for offline support
- [ ] Implement virtual scrolling for very large lists (1000+ items)
- [ ] Add image lazy loading with Intersection Observer
- [ ] Implement HTTP/2 server push for critical resources
- [ ] Add CDN configuration (Cloudflare/CloudFront)
- [ ] Implement progressive web app (PWA) features
