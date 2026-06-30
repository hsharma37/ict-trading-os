import { useEffect, useRef } from 'react'
import { createChart, IChartApi, CandlestickData, HistogramData } from 'lightweight-charts'
import { marketApi } from '@/api/client'

interface Props {
  symbol: string
  timeframe?: string
  height?: number
  showVolume?: boolean
}

export default function TradingViewChart({ symbol, timeframe = '1h', height = 400, showVolume = true }: Props) {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!chartContainerRef.current) return

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height,
      layout: {
        background: { color: 'transparent' },
        textColor: 'rgba(255, 255, 255, 0.8)',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
        timeVisible: true,
      },
    })

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    })

    let volumeSeries: any = null
    if (showVolume) {
      volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: { type: 'volume' },
        priceScaleId: '',
        scaleMargins: { top: 0.8, bottom: 0 },
      })
    }

    chartRef.current = chart

    // Load historical data
    marketApi.history(symbol, timeframe).then((res: any) => {
      const candles = res.data?.candles || []
      if (candles.length > 0) {
        const data: CandlestickData[] = candles.map((c: any) => ({
          time: c.time as number,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }))
        candlestickSeries.setData(data)

        if (showVolume && volumeSeries) {
          const volumeData: HistogramData[] = candles.map((c: any) => ({
            time: c.time as number,
            value: c.volume || 0,
            color: c.close >= c.open ? 'rgba(34, 197, 94, 0.5)' : 'rgba(239, 68, 68, 0.5)',
          }))
          volumeSeries.setData(volumeData)
        }

        chart.timeScale().fitContent()
      }
    })

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth })
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [symbol, timeframe, height, showVolume])

  return <div ref={chartContainerRef} style={{ width: '100%', height }} />
}
