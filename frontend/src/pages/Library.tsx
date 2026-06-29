import { useState, useMemo, useEffect } from 'react'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import {
  BookOpen, Search, ChevronDown, ChevronUp, Brain,
  X, CheckCircle, AlertCircle, Star, Filter
} from 'lucide-react'

interface Concept {
  name: string
  abbr: string
  cats: string[]
  desc: string
  example: string
  quiz?: {
    q: string
    options: string[]
    correct: number
  }
}

const ALL_CONCEPTS: Concept[] = [
  {
    name: 'Fair Value Gap',
    abbr: 'FVG / IFVG',
    cats: ['Liquidity', 'Structure'],
    desc: 'A three-candle imbalance where the middle candle creates a gap between the wicks of the first and third candle. Price often returns to fill (mitigate) FVGs before continuing the original direction.',
    example: 'On a bullish FVG: candle 1 high, candle 2 large bullish displacement, candle 3 low — the gap between candle 1\'s high and candle 3\'s low is the FVG.',
    quiz: {
      q: 'A bullish FVG forms after which kind of candle sequence?',
      options: ['A slow, low-range three candles', 'A strong displacement candle leaving a gap between candle 1 and candle 3', 'Three candles of equal size'],
      correct: 1,
    },
  },
  {
    name: 'Order Block',
    abbr: 'OB / IOB',
    cats: ['Liquidity', 'POI'],
    desc: 'The last down candle before a bullish impulse (bullish OB) or the last up candle before a bearish impulse (bearish OB).',
    example: 'If price drops, then reverses up aggressively, the last red candle before that reversal is the bullish OB.',
    quiz: {
      q: 'A bearish Order Block is:',
      options: ['The last up candle before a bearish impulse', 'The last down candle before a bullish impulse', 'Any large red candle'],
      correct: 0,
    },
  },
  {
    name: 'Market Structure Shift',
    abbr: 'MSS / BOS',
    cats: ['Structure'],
    desc: 'An MSS occurs when price breaks through the most recent significant swing high/low with displacement, signaling a likely trend change.',
    example: 'In a downtrend with lower highs, a new high suddenly breaks above the most recent lower high with strong momentum — that\'s an MSS suggesting bullish intent.',
    quiz: {
      q: 'MSS is primarily used to:',
      options: ['Confirm a trend reversal/shift in delivery', 'Calculate position size', 'Identify session times'],
      correct: 0,
    },
  },
  {
    name: 'Liquidity',
    abbr: 'BSL / SSL',
    cats: ['Liquidity'],
    desc: 'Buy-side liquidity (BSL) pools above equal highs and old swing highs. Sell-side liquidity (SSL) pools below equal lows.',
    example: 'Equal highs at a round number often attract price like a magnet before a reversal.',
    quiz: {
      q: 'Sell-side liquidity (SSL) typically rests:',
      options: ['Above recent highs', 'Below recent lows', 'At the 50% level of a range'],
      correct: 1,
    },
  },
  {
    name: 'Optimal Trade Entry',
    abbr: 'OTE',
    cats: ['Fibonacci', 'POI'],
    desc: 'The 61.8%–79% Fibonacci retracement zone of an impulse leg, ideally combined with another ICT model like an FVG or OB.',
    example: 'After a strong up-leg, price retraces to the 70% Fib level where a bullish FVG also sits — that confluence zone is the OTE entry.',
    quiz: {
      q: 'OTE refers to a retracement zone around:',
      options: ['10%–20%', '38%–50%', '61.8%–79%'],
      correct: 2,
    },
  },
  {
    name: 'Power of 3',
    abbr: 'PO3',
    cats: ['Manipulation', 'Sessions'],
    desc: 'Accumulation → Manipulation → Distribution. A session often ranges quietly, fakes a move (manipulation/Judas swing), then distributes in the real direction.',
    example: 'Asian session accumulates a tight range. London "manipulates" with a fake breakout down. New York then distributes price upward.',
    quiz: {
      q: 'In PO3, the "Manipulation" phase usually:',
      options: ['Confirms the real direction immediately', 'Is a false move opposite the real intended direction', 'Only happens on Fridays'],
      correct: 1,
    },
  },
  {
    name: 'Kill Zones',
    abbr: 'KZ',
    cats: ['Sessions', 'Time'],
    desc: 'High-probability time windows: London Open, NY AM, NY PM, Asian range. Setups are considered more reliable inside these windows.',
    example: 'A perfect-looking FVG setup at 2pm EST outside any kill zone is statistically less reliable than the same setup during NY AM open.',
    quiz: {
      q: 'Trading outside a kill zone window is generally considered:',
      options: ['Equally reliable', 'Lower probability', 'Higher probability'],
      correct: 1,
    },
  },
  {
    name: 'Breaker Block',
    abbr: 'BB',
    cats: ['Structure', 'POI'],
    desc: 'A failed order block — when an OB is violated, it converts into a breaker, and price returning to that zone often reacts opposite to the original OB.',
    example: 'A bullish OB gets broken downward; on a later retest, that zone now acts as resistance (a bearish breaker).',
    quiz: {
      q: 'A breaker block forms when:',
      options: ['Price respects an OB perfectly', 'An order block is violated/broken', 'Two FVGs overlap'],
      correct: 1,
    },
  },
  {
    name: 'Premium & Discount',
    abbr: 'P&D',
    cats: ['Fibonacci', 'Context'],
    desc: 'The 50% (equilibrium) level of any swing divides the range into premium (above 50%, favor selling) and discount (below 50%, favor buying).',
    example: 'If HTF bias is bullish, you generally want to buy from a discount POI, not chase price already deep into premium.',
    quiz: {
      q: 'If bias is bullish, ICT generally favors entries from:',
      options: ['Premium', 'Discount', 'It does not matter'],
      correct: 1,
    },
  },
  {
    name: 'CISD (CHoCH)',
    abbr: 'CISD',
    cats: ['Structure'],
    desc: 'Change in State of Delivery — when price shifts direction, confirmed by closing through the most recent structural pivot.',
    example: 'A string of bearish closes suddenly gives way to a candle closing back above the last minor high — that close-based shift is CISD.',
    quiz: {
      q: 'CISD is confirmed primarily by:',
      options: ['Candle wicks only', 'A close through a key structural pivot', 'Volume spikes'],
      correct: 1,
    },
  },
  {
    name: 'Institutional Order Flow',
    abbr: 'IOF',
    cats: ['Manipulation', 'Context'],
    desc: 'The direction in which smart money are net positioned, inferred from price delivery, displacement, and which imbalances get mitigated vs respected.',
    example: 'If every dip is bought aggressively and FVGs below price are left unfilled while price keeps climbing, that\'s a bullish IOF read.',
    quiz: {
      q: 'IOF is best inferred from:',
      options: ['News headlines', 'Price delivery patterns and displacement', 'The time of day alone'],
      correct: 1,
    },
  },
  {
    name: 'Judas Swing',
    abbr: 'JS',
    cats: ['Manipulation', 'Sessions'],
    desc: 'A false move at session open opposite to the true intended direction for the day, designed to trap retail traders before the real move.',
    example: 'London opens, price spikes down sharply (triggering breakout sellers), then reverses hard upward for the rest of the session.',
    quiz: {
      q: 'A Judas Swing typically occurs:',
      options: ['Mid-session with no catalyst', 'At/near a session open, against the real intended direction', 'Only on Mondays'],
      correct: 1,
    },
  },
  {
    name: 'Silver Bullet',
    abbr: 'SB',
    cats: ['Sessions', 'Time'],
    desc: 'A specific 1-hour kill zone (10–11am or 2–3pm EST) where ICT looks for a fast MSS + FVG combination to develop and resolve within that single hour.',
    example: 'At 10:05am EST, price sweeps a small liquidity pool, shifts structure, leaves an FVG, and reaches target by 10:50am — a textbook Silver Bullet sequence.',
    quiz: {
      q: 'The Silver Bullet windows are:',
      options: ['Any random hour', 'Specifically 10–11am and 2–3pm EST', 'Only at market close'],
      correct: 1,
    },
  },
  {
    name: 'Turtle Soup',
    abbr: 'TS',
    cats: ['Manipulation', 'Structure'],
    desc: 'A reversal pattern where price breaks beyond a well-known recent high/low, fails to continue, and reverses back inside the prior range — fading a failed breakout.',
    example: 'Price breaks the prior day\'s low, triggers stops, then closes back above it within a few candles — that failed breakdown is a Turtle Soup setup.',
    quiz: {
      q: 'Turtle Soup specifically trades:',
      options: ['Continuation of a strong breakout', 'A failed breakout that reverses back inside the range', 'Range-bound consolidation only'],
      correct: 1,
    },
  },
  {
    name: 'Venom Model',
    abbr: 'VM',
    cats: ['Structure', 'Context'],
    desc: 'Requires alignment of a Market Structure Shift on a higher timeframe AND a matching MSS on a lower entry timeframe before entering — double timeframe confirmation.',
    example: '1H structure shifts bullish, then the 5M also prints its own bullish MSS shortly after — only then is a long considered under the Venom model.',
    quiz: {
      q: 'The Venom model requires:',
      options: ['Only a single timeframe MSS', 'MSS alignment across two different timeframes', 'No structural confirmation at all'],
      correct: 1,
    },
  },
]

const EXTRA_CONCEPTS: Concept[] = [
  {
    name: 'Displacement',
    abbr: 'DISP',
    cats: ['Structure', 'Context'],
    desc: 'Aggressive, fast price movement with strong candles, often indicating institutional order flow. Displacement typically leaves behind FVGs and signals directional intent.',
    example: 'A sudden strong bearish candle that breaks through a recent swing low with no retracement — this is displacement showing bearish intent.',
  },
  {
    name: 'Inducement',
    abbr: 'IND',
    cats: ['Manipulation', 'Liquidity'],
    desc: 'A false move designed to trap retail traders by creating the illusion of a setup. Inducement sweeps liquidity before the real move in the opposite direction.',
    example: 'Price pushes slightly above a previous high, stops out breakout traders, then reverses sharply — that push above the high was inducement.',
  },
  {
    name: 'Mitigation',
    abbr: 'MIT',
    cats: ['Structure', 'Liquidity'],
    desc: 'When price returns to fill an imbalance (FVG) or retest an order block. Mitigation confirms the original structure and often provides the entry for the next leg.',
    example: 'After a strong bullish displacement, price retraces back into the FVG left behind — this mitigation provides the optimal long entry.',
  },
  {
    name: 'Imbalance',
    abbr: 'IMB',
    cats: ['Structure', 'Liquidity'],
    desc: 'A price gap where buying and selling were not evenly matched. Imbalances appear as FVGs on lower timeframes and act as magnets for price.',
    example: 'After a news event, price gaps up leaving a void between the previous close and the new open — that gap is an imbalance that often gets filled.',
  },
]

const ALL = [...ALL_CONCEPTS, ...EXTRA_CONCEPTS]

function getCatColor(cat: string): string {
  const map: Record<string, string> = {
    'Liquidity': 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    'Structure': 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    'POI': 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    'Fibonacci': 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    'Manipulation': 'bg-red-500/10 text-red-400 border-red-500/20',
    'Sessions': 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
    'Time': 'bg-slate-500/10 text-slate-400 border-slate-500/20',
    'Context': 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  }
  return map[cat] || 'bg-gray-500/10 text-gray-400 border-gray-500/20'
}

export default function Library() {
  const [search, setSearch] = useState('')
  const [activeCats, setActiveCats] = useState<string[]>([])
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [quizOpen, setQuizOpen] = useState<Concept | null>(null)
  const [selectedOption, setSelectedOption] = useState<number | null>(null)
  const [quizScore, setQuizScore] = useState({ correct: 0, total: 0 })
  const [quizHistory, setQuizHistory] = useState<Set<string>>(new Set())

  const allCats = useMemo(() => {
    const s = new Set<string>()
    ALL.forEach((c) => c.cats.forEach((cat) => s.add(cat)))
    return Array.from(s).sort()
  }, [])

  const filtered = useMemo(() => {
    let concepts = ALL
    if (search.trim()) {
      const q = search.toLowerCase()
      concepts = concepts.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.abbr.toLowerCase().includes(q) ||
          c.desc.toLowerCase().includes(q) ||
          c.cats.some((cat) => cat.toLowerCase().includes(q))
      )
    }
    if (activeCats.length > 0) {
      concepts = concepts.filter((c) => c.cats.some((cat) => activeCats.includes(cat)))
    }
    return concepts
  }, [search, activeCats])

  const toggleCat = (cat: string) => {
    setActiveCats((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    )
  }

  const toggleExpanded = (name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(name)) {
        next.delete(name)
      } else {
        next.add(name)
      }
      return next
    })
  }

  const openQuiz = (concept: Concept) => {
    if (!concept.quiz) return
    setQuizOpen(concept)
    setSelectedOption(null)
  }

  const answerQuiz = (idx: number) => {
    if (!quizOpen || selectedOption !== null) return
    setSelectedOption(idx)
    const isCorrect = idx === quizOpen.quiz!.correct
    if (isCorrect) {
      setQuizScore((prev) => ({ correct: prev.correct + 1, total: prev.total + 1 }))
      setQuizHistory((prev) => new Set(prev).add(quizOpen.name))
    } else {
      setQuizScore((prev) => ({ correct: prev.correct, total: prev.total + 1 }))
    }
  }

  const closeQuiz = () => {
    setQuizOpen(null)
    setSelectedOption(null)
  }

  // Close quiz on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeQuiz()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const masteredCount = quizHistory.size

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <BookOpen className="w-6 h-6 text-primary" />
            ICT Library
          </h1>
          <p className="text-muted-foreground">
            Concept reference & interactive quizzes
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="px-3 py-1.5 rounded-lg bg-primary/10 border border-primary/20 text-sm">
            <span className="text-primary font-semibold">{masteredCount}</span>
            <span className="text-muted-foreground"> / {ALL.length} mastered</span>
          </div>
          <div className="px-3 py-1.5 rounded-lg bg-muted border border-border text-sm">
            <span className="text-muted-foreground">Score: </span>
            <span className="font-semibold">{quizScore.correct}</span>
            <span className="text-muted-foreground"> / {quizScore.total}</span>
          </div>
        </div>
      </div>

      {/* Search & Filters */}
      <Card>
        <CardContent className="pt-6 space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search: FVG, OB, liquidity, MSS..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border rounded-md bg-background text-sm"
            />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Filter className="w-4 h-4 text-muted-foreground" />
            {allCats.map((cat) => {
              const active = activeCats.includes(cat)
              return (
                <button
                  key={cat}
                  onClick={() => toggleCat(cat)}
                  className={`px-2.5 py-1 rounded-full text-xs border transition-all ${
                    active
                      ? getCatColor(cat)
                      : 'bg-muted text-muted-foreground border-border hover:border-foreground/30'
                  }`}
                >
                  {cat}
                </button>
              )
            })}
            {activeCats.length > 0 && (
              <button
                onClick={() => setActiveCats([])}
                className="text-xs text-muted-foreground hover:text-foreground underline"
              >
                Clear filters
              </button>
            )}
          </div>
          <div className="text-xs text-muted-foreground">
            Showing {filtered.length} of {ALL.length} concepts
          </div>
        </CardContent>
      </Card>

      {/* Concept Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filtered.map((concept) => {
          const isExpanded = expanded.has(concept.name)
          const isMastered = quizHistory.has(concept.name)
          return (
            <div
              key={concept.name}
              className={`group border rounded-lg p-4 cursor-pointer transition-all ${
                isExpanded
                  ? 'border-primary/40 bg-primary/5'
                  : 'border-border bg-card hover:border-foreground/20 hover:-translate-y-0.5'
              }`}
              onClick={() => toggleExpanded(concept.name)}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-sm">{concept.name}</h3>
                    {isMastered && (
                      <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400" />
                    )}
                  </div>
                  <div className="text-xs text-primary font-medium mt-0.5">{concept.abbr}</div>
                </div>
                {isExpanded ? (
                  <ChevronUp className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-1" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-1" />
                )}
              </div>

              <div className="flex flex-wrap gap-1 mt-2">
                {concept.cats.map((cat) => (
                  <span
                    key={cat}
                    className={`px-1.5 py-0.5 rounded-full text-[10px] border ${getCatColor(cat)}`}
                  >
                    {cat}
                  </span>
                ))}
              </div>

              <p className="text-xs text-muted-foreground mt-2 line-clamp-3">{concept.desc}</p>

              {isExpanded && (
                <div className="mt-3 space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
                  <div className="p-3 rounded-md bg-muted/50 border border-border/50">
                    <div className="text-[10px] font-semibold uppercase text-muted-foreground mb-1">
                      Example
                    </div>
                    <div className="text-xs text-foreground leading-relaxed">{concept.example}</div>
                  </div>
                  {concept.quiz ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="w-full"
                      onClick={(e) => {
                        e.stopPropagation()
                        openQuiz(concept)
                      }}
                    >
                      <Brain className="w-3.5 h-3.5 mr-1.5" />
                      Quiz me on this
                    </Button>
                  ) : (
                    <div className="text-xs text-muted-foreground italic">
                      No quiz available for this concept yet.
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {filtered.length === 0 && (
        <div className="text-center py-12 text-muted-foreground">
          <BookOpen className="w-8 h-8 mx-auto mb-3 opacity-50" />
          <p>No concepts match your search.</p>
          <Button variant="ghost" size="sm" onClick={() => { setSearch(''); setActiveCats([]) }} className="mt-2">
            Clear filters
          </Button>
        </div>
      )}

      {/* Quiz Modal */}
      {quizOpen && quizOpen.quiz && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={closeQuiz}
        >
          <div
            className="bg-card border border-border rounded-xl p-6 max-w-md w-[90%] shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <div className="text-xs text-primary font-semibold uppercase">{quizOpen.name}</div>
              <button
                onClick={closeQuiz}
                className="p-1 rounded-md hover:bg-muted text-muted-foreground"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-sm font-semibold mb-4">{quizOpen.quiz.q}</div>

            <div className="space-y-2">
              {quizOpen.quiz.options.map((opt, idx) => {
                const isSelected = selectedOption === idx
                const isCorrect = idx === quizOpen.quiz!.correct
                const showCorrect = selectedOption !== null && isCorrect
                const showIncorrect = selectedOption !== null && isSelected && !isCorrect

                return (
                  <button
                    key={idx}
                    onClick={() => answerQuiz(idx)}
                    disabled={selectedOption !== null}
                    className={`w-full text-left px-4 py-3 rounded-md border text-sm transition-all ${
                      showCorrect
                        ? 'border-emerald-500 bg-emerald-500/10 text-emerald-400'
                        : showIncorrect
                          ? 'border-red-500 bg-red-500/10 text-red-400'
                          : isSelected
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-border bg-muted/50 hover:border-primary/60 hover:text-foreground'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {showCorrect && <CheckCircle className="w-4 h-4 flex-shrink-0" />}
                      {showIncorrect && <AlertCircle className="w-4 h-4 flex-shrink-0" />}
                      <span>{opt}</span>
                    </div>
                  </button>
                )
              })}
            </div>

            {selectedOption !== null && (
              <div className="mt-4 text-center">
                {selectedOption === quizOpen.quiz.correct ? (
                  <div className="text-sm text-emerald-400 font-medium">Correct! Well done.</div>
                ) : (
                  <div className="text-sm text-red-400">
                    Incorrect. The correct answer is: <strong>{quizOpen.quiz.options[quizOpen.quiz.correct]}</strong>
                  </div>
                )}
              </div>
            )}

            <div className="mt-4 flex justify-end">
              <Button variant="ghost" size="sm" onClick={closeQuiz}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
