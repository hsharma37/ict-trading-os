import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'

export default function Plan() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Trading Plan</h1>
        <p className="text-muted-foreground">Set your daily bias, killzones, and confluence</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Daily Plan</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Session</label>
              <select className="w-full px-3 py-2 border rounded-md bg-background">
                <option value="combined">Combined</option>
                <option value="london">London</option>
                <option value="ny">New York</option>
                <option value="asia">Asia</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Bias Direction</label>
              <select className="w-full px-3 py-2 border rounded-md bg-background">
                <option value="neutral">Neutral</option>
                <option value="bullish">Bullish</option>
                <option value="bearish">Bearish</option>
              </select>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Narrative</label>
            <textarea
              className="w-full px-3 py-2 border rounded-md bg-background min-h-[100px]"
              placeholder="Describe your market narrative..."
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Killzones</label>
            <div className="flex gap-2">
              {['London Open', 'NY Open', 'London Close', 'NY Close'].map((kz) => (
                <label key={kz} className="flex items-center gap-2 px-3 py-2 border rounded-md cursor-pointer hover:bg-muted">
                  <input type="checkbox" className="rounded" />
                  <span className="text-sm">{kz}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Confluence Tags</label>
            <div className="flex gap-2 flex-wrap">
              {['PD Array', 'MSS', 'FVG', 'OB', 'Liquidity', 'Order Flow', 'SMT'].map((tag) => (
                <label key={tag} className="flex items-center gap-2 px-3 py-2 border rounded-md cursor-pointer hover:bg-muted">
                  <input type="checkbox" className="rounded" />
                  <span className="text-sm">{tag}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Max Trades</label>
              <input
                type="number"
                defaultValue={3}
                className="w-full px-3 py-2 border rounded-md bg-background"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Daily Loss Limit ($)</label>
              <input
                type="number"
                placeholder="e.g. 200"
                className="w-full px-3 py-2 border rounded-md bg-background"
              />
            </div>
          </div>

          <Button>Save Plan</Button>
        </CardContent>
      </Card>
    </div>
  )
}
