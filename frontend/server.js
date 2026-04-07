const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');

const app = express();
const PORT = 3000;
const BACKEND_URL = process.env.BACKEND_INTERNAL_URL || 'http://backend:8001';

// Proxy /api/* to backend
app.use('/api', createProxyMiddleware({
  target: BACKEND_URL,
  changeOrigin: true,
  timeout: 120000,
  proxyTimeout: 120000,
  onError: (err, req, res) => {
    console.error('Proxy error:', err.message);
    res.status(502).json({ error: 'Backend unavailable' });
  }
}));

// Proxy /uploads/* to backend
app.use('/uploads', createProxyMiddleware({
  target: BACKEND_URL,
  changeOrigin: true,
}));

// Serve static files
app.use(express.static(path.join(__dirname, 'build'), {
  maxAge: '1y',
  immutable: true
}));

// SPA fallback
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'build', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Frontend server running on port ${PORT}`);
  console.log(`API proxy target: ${BACKEND_URL}`);
});
