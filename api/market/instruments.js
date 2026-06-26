import { getInstruments } from '../../lib/yahoo-finance.js';

export default function handler(req, res) {
  return res.status(200).json({ instruments: getInstruments() });
}
