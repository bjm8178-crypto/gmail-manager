# CDN Setup Guide for Gmail Manager

## Overview
Configure a CDN (Content Delivery Network) to cache and serve static assets globally for faster load times.

---

## Option 1: Cloudflare CDN (Recommended - Free Tier Available)

### Setup Steps

1. **Sign up for Cloudflare**
   - Visit https://dash.cloudflare.com/sign-up
   - Create account (free)

2. **Add Your Domain**
   - Click "Add a site"
   - Enter: `gmail-manager-gamma.vercel.app`
   - Select Free plan

3. **Update DNS**
   - Cloudflare will provide nameservers
   - Update at your domain registrar
   - Wait for propagation (5-30 minutes)

4. **Configure Caching Rules**
   - Go to Caching > Configuration
   - Set Browser Cache TTL: 4 hours
   - Set Caching Level: Standard

5. **Page Rules** (Optional)
   - Create rule for `*.js`: Cache Level = Cache Everything, Edge Cache TTL = 1 month
   - Create rule for `*.css`: Cache Level = Cache Everything, Edge Cache TTL = 1 month
   - Create rule for `*.png|jpg|jpeg|gif|svg`: Cache Level = Cache Everything, Edge Cache TTL = 1 year

### Vercel Integration
```bash
# In Vercel project settings
# Domains > Add Cloudflare domain
# Cloudflare will auto-configure
```

---

## Option 2: Vercel Edge Network (Built-in)

### Configuration

Vercel already provides edge caching. Optimize with `vercel.json`:

```json
{
  "headers": [
    {
      "source": "/assets/(.*)",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    },
    {
      "source": "/(.*).js",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    },
    {
      "source": "/(.*).css",
      "headers": [
        {
          "key": "Cache-Control",
          "value": "public, max-age=31536000, immutable"
        }
      ]
    }
  ]
}
```

Add this to `gmail-manager/vercel.json` (merge with existing config).

---

## Option 3: CloudFront (AWS)

### Setup Steps

1. **Create CloudFront Distribution**
   ```bash
   # AWS Console > CloudFront > Create Distribution
   Origin Domain: gmail-manager-gamma.vercel.app
   Origin Protocol: HTTPS only
   Viewer Protocol: Redirect HTTP to HTTPS
   ```

2. **Configure Cache Behaviors**
   - Path pattern: `/assets/*`
   - TTL: Min 0, Max 31536000, Default 86400

3. **Update Vercel Environment Variables**
   ```bash
   VITE_CDN_URL=https://your-cloudfront-id.cloudfront.net
   ```

---

## Image Optimization

### Install sharp (if using SSR)
```bash
npm install sharp
```

### Update vite.config.js
```javascript
import imagemin from 'vite-plugin-imagemin';

export default defineConfig({
  plugins: [
    react(),
    imagemin({
      gifsicle: { optimizationLevel: 7 },
      mozjpeg: { quality: 80 },
      pngquant: { quality: [0.8, 0.9], speed: 4 },
      svgo: {
        plugins: [
          { name: 'removeViewBox', active: false },
          { name: 'removeEmptyAttrs', active: true }
        ]
      }
    })
  ],
});
```

---

## Asset Preloading

### Add to `index.html`
```html
<head>
  <!-- Preload critical assets -->
  <link rel="preload" href="/assets/fonts/inter.woff2" as="font" type="font/woff2" crossorigin>
  
  <!-- DNS prefetch for API -->
  <link rel="dns-prefetch" href="https://gmail-manager-production.up.railway.app">
  
  <!-- Preconnect to API -->
  <link rel="preconnect" href="https://gmail-manager-production.up.railway.app">
</head>
```

---

## Lazy Loading Images

### Create LazyImage component

```jsx
// frontend/src/components/LazyImage.jsx
import { useState, useEffect, useRef } from 'react';

export default function LazyImage({ src, alt, className, placeholder }) {
  const [imageSrc, setImageSrc] = useState(placeholder || '/placeholder.png');
  const [loading, setLoading] = useState(true);
  const imgRef = useRef();

  useEffect(() => {
    let observer;
    
    if (imgRef.current) {
      observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              setImageSrc(src);
              setLoading(false);
              observer.disconnect();
            }
          });
        },
        { threshold: 0.1 }
      );
      
      observer.observe(imgRef.current);
    }

    return () => {
      if (observer && imgRef.current) {
        observer.disconnect();
      }
    };
  }, [src]);

  return (
    <img
      ref={imgRef}
      src={imageSrc}
      alt={alt}
      className={`${className} ${loading ? 'blur-sm' : ''} transition-all`}
      loading="lazy"
    />
  );
}
```

---

## Service Worker (PWA)

### Install Workbox
```bash
npm install workbox-webpack-plugin
```

### Update vite.config.js
```javascript
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/gmail-manager-production\.up\.railway\.app\/api\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 5 // 5 minutes
              }
            }
          }
        ]
      }
    })
  ]
});
```

---

## Testing CDN Performance

### Check Cache Headers
```bash
curl -I https://gmail-manager-gamma.vercel.app/assets/index-abc123.js
# Look for:
# Cache-Control: public, max-age=31536000, immutable
# CF-Cache-Status: HIT (if using Cloudflare)
```

### WebPageTest
1. Visit https://www.webpagetest.org
2. Enter URL: https://gmail-manager-gamma.vercel.app
3. Run test
4. Check "Time to First Byte" and "Start Render"

---

## Performance Checklist

- [x] Vite code splitting configured
- [ ] CDN configured (Cloudflare/Vercel)
- [ ] Cache headers set
- [ ] Image optimization enabled
- [ ] Lazy loading implemented
- [ ] Service worker configured (optional)
- [ ] DNS prefetch added
- [ ] Preload critical assets

---

## Expected Performance Improvements

| Optimization | Improvement |
|--------------|-------------|
| CDN Edge Caching | 40-60% faster first load (global users) |
| Image Optimization | 30-50% smaller image sizes |
| Lazy Loading | 50-70% faster initial page load |
| Service Worker | Instant repeat visits |
| Asset Preloading | 200-500ms faster perceived load |
