import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'

export default function Execute() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Execution Console</h1>
        <p className="text-muted-foreground">Place and manage trades</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Order Entry</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">Symbol</label>
                <input
                  type="text"
                  placeholder="EURUSD"
                  className="w-full px-3 py-2 border rounded-md bg-background"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Direction</label>
                <select className="w-full px-3 py-2 border rounded-md bg-background">
                  <option value="long">Long</option>
                  <option value="short">Short</option>
                </select>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <div className="space-y-2">
                <label className="text-sm font-medium">Entry Price</label>
                <input type="number" step="0.00001" className="w-full px-3 py-2 border rounded-md bg-background" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Stop Loss</label>
                <input type="number" step="0.00001" className="w-full px-3 py-2 border rounded-md bg-background" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Take Profit 1</label>
                <input type="number" step="0.00001" className="w-full px-3 py-2 border rounded-md bg-background" />
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">Lot Size</label>
                <input type="number" step="0.01" className="w-full px-3 py-2 border rounded-md bg-background" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Leverage</label>
                <input type="range" min="1" max="100" defaultValue="1" className="w-full" />
                <div className="text-xs text-muted-foreground">1x</div>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Risk Amount ($)</label>
              <input type="number" className="w-full px-3 py-2 border rounded-md bg-background" />
            </div>

            <Button className="w-full">Place Order</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Lot Calculator</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Account Balance</label>
              <input type="number" className="w-full px-3 py-2 border rounded-md bg-background" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Risk %</label>
              <input type="number" step="0.1" className="w-full px-3 py-2 border rounded-md bg-background" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Stop Loss (pips)</label>
              <input type="number" className="w-full px-3 py-2 border rounded-md bg-background" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Leverage</label>
              <input type="range" min="1" max="100" defaultValue="1" className="w-full" />
            </div>
            <div className="p-4 bg-muted rounded-md">
              <div className="text-sm font-medium">Calculated Lot Size</div>
              <div className="text-2xl font-bold">0.00</div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
