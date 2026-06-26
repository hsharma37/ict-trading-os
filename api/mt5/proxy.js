export default async function handler(req, res) {
  const MT5_BRIDGE_URL = process.env.MT5_BRIDGE_URL;
  if (!MT5_BRIDGE_URL) {
    return res.status(500).json({ error: 'MT5_BRIDGE_URL is not configured' });
  }

  const targetUrl = `${MT5_BRIDGE_URL}${req.url.replace('/api/mt5', '')}`;
  const options = {
    method: req.method,
    headers: { ...req.headers },
    body: ['GET', 'HEAD'].includes(req.method) ? undefined : JSON.stringify(req.body)
  };

  delete options.headers.host;

  try {
    const response = await fetch(targetUrl, options);
    const data = await response.json();
    res.status(response.status).json(data);
  } catch (error) {
    res.status(500).json({ error: error.message || 'MT5 proxy request failed' });
  }
}
