export interface Trade {
  id: string
  user_id: string
  plan_id?: string
  symbol: string
  direction: 'long' | 'short'
  entry_price?: number
  stop_loss?: number
  take_profit_1?: number
  take_profit_2?: number
  take_profit_3?: number
  lot_size?: number
  leverage: number
  risk_amount?: number
  status: 'pending' | 'open' | 'closed' | 'cancelled'
  outcome?: 'win' | 'loss' | 'breakeven'
  pnl?: number
  pnl_pips?: number
  exit_price?: number
  exit_time?: string
  entry_time: string
  created_at: string
}

export interface TradingPlan {
  id: string
  user_id: string
  date: string
  session: 'london' | 'ny' | 'asia' | 'combined'
  bias_direction: 'bullish' | 'bearish' | 'neutral'
  narrative?: string
  confluence_tags: string[]
  killzones: string[]
  max_trades: number
  daily_loss_limit?: number
  created_at: string
  updated_at: string
}

export interface JournalEntry {
  id: string
  trade_id?: string
  user_id: string
  pre_trade_notes?: string
  post_trade_notes?: string
  emotion_score?: number
  setup_grade?: number
  execution_grade?: number
  management_grade?: number
  tags: string[]
  lessons?: string
  created_at: string
}
