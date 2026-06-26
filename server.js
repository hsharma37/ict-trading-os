import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PUBLIC_DIR = path.join(__dirname, 'public');
const ROOT_HTML = path.join(__dirname, 'ICT_Trading_OS_v7.html');
const INDEX_HTML = path.join(PUBLIC_DIR, 'index.html');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

function sendText(res, status, text, contentType = 'text/plain; charset=utf-8') {
  res.writeHead(status, {
    'Content-Type': contentType,
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  });
  res.end(text);
}

function sendJson(res, status, data) {
  sendText(res, status, JSON.stringify(data), 'application/json; charset=utf-8');
}

async function sendFile(res, filePath) {
  try {
    const data = await fs.readFile(filePath);
    const ext = path.extname(filePath).toLowerCase();
    const type = MIME_TYPES[ext] || 'application/octet-stream';
    res.writeHead(200, {
      'Content-Type': type,
      'Access-Control-Allow-Origin': '*',
    });
    res.end(data);
  } catch (error) {
    if (error.code === 'ENOENT') {
      sendText(res, 404, 'Not Found');
    } else {
      sendText(res, 500, 'Server Error');
    }
  }
}

function parseQuery(url) {
  const query = Object.create(null);
  const searchParams = new URL(url, 'http://localhost').searchParams;
  for (const [key, value] of searchParams.entries()) {
    query[key] = value;
  }
  return query;
}

async function getRequestBody(req) {
  if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
    return undefined;
  }

  return await new Promise((resolve, reject) => {
    let body = '';
    req.on('data', (chunk) => {
      body += chunk.toString();
    });
    req.on('end', () => resolve(body || undefined));
    req.on('error', reject);
  });
}

async function proxyMt5(req, res, pathname) {
  const MT5_BRIDGE_URL = process.env.MT5_BRIDGE_URL || 'http://localhost:5000';
  const parsedUrl = new URL(req.url, 'http://localhost');
  const targetPath = pathname.replace('/api/mt5', '') || '/';
  const targetUrl = `${MT5_BRIDGE_URL}${targetPath}${parsedUrl.search}`;
  const body = await getRequestBody(req);

  const headers = { ...req.headers };
  delete headers.host;

  try {
    const response = await fetch(targetUrl, {
      method: req.method,
      headers,
      body,
    });

    const buffer = Buffer.from(await response.arrayBuffer());
    const responseHeaders = {};
    response.headers.forEach((value, key) => {
      responseHeaders[key] = value;
    });

    res.writeHead(response.status, responseHeaders);
    res.end(buffer);
  } catch (error) {
    console.error('MT5 proxy error:', error);
    sendJson(res, 500, { error: 'MT5 proxy request failed', details: error.message });
  }
}

async function handleApi(req, res, pathname) {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    });
    return res.end();
  }

  if (pathname.startsWith('/api/mt5')) {
    return proxyMt5(req, res, pathname);
  }

  const query = parseQuery(req.url);
  let handlerPath = null;
  let routeParams = {};

  if (pathname === '/api/market/instruments') {
    handlerPath = './api/market/instruments.js';
  } else if (pathname === '/api/market/prices') {
    handlerPath = './api/market/prices.js';
  } else if (pathname.startsWith('/api/market/price/')) {
    const symbol = decodeURIComponent(pathname.replace('/api/market/price/', '')).trim();
    if (!symbol) {
      return sendJson(res, 400, { error: 'Symbol is required' });
    }
    handlerPath = './api/market/price/[symbol].js';
    routeParams.symbol = symbol;
  }

  if (!handlerPath) {
    return sendText(res, 404, 'Not Found');
  }

  try {
    const module = await import(handlerPath);
    const handler = module.default;
    const reqWrapper = {
      method: req.method,
      headers: req.headers,
      url: req.url,
      query: { ...query, ...routeParams },
    };

    let statusCode = 200;
    const headers = {
      'Content-Type': 'application/json; charset=utf-8',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    const resWrapper = {
      status(code) {
        statusCode = code;
        return this;
      },
      json(data) {
        res.writeHead(statusCode, headers);
        res.end(JSON.stringify(data));
      },
      setHeader(key, value) {
        headers[key] = value;
      },
    };

    await handler(reqWrapper, resWrapper);
  } catch (error) {
    console.error('API handler error:', error);
    sendJson(res, 500, { error: 'Server Error', details: error.message });
  }
}

async function requestListener(req, res) {
  const parsedUrl = new URL(req.url, 'http://localhost');
  const pathname = parsedUrl.pathname;

  if (pathname === '/' || pathname === '/index.html') {
    return sendFile(res, ROOT_HTML);
  }

  if (pathname === '/ICT_Trading_OS_v7.html') {
    return sendFile(res, ROOT_HTML);
  }

  if (pathname.startsWith('/api/')) {
    return handleApi(req, res, pathname);
  }

  const staticPath = path.join(PUBLIC_DIR, pathname);
  if (staticPath.startsWith(PUBLIC_DIR)) {
    try {
      const stat = await fs.stat(staticPath);
      if (stat.isFile()) {
        return sendFile(res, staticPath);
      }
    } catch {
      // continue to 404
    }
  }

  return sendText(res, 404, 'Not Found');
}

const port = Number(process.env.PORT || 8000);
const server = http.createServer(requestListener);

server.listen(port, () => {
  console.log(`Server listening on http://localhost:${port}`);
});
