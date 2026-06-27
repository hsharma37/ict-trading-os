import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'

export default function Settings() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">Configure your trading environment</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Risk Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Default Risk %</label>
              <input type="number" step="0.1" defaultValue={1} className="w-full px-3 py-2 border rounded-md bg-background" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Max Daily Loss ($)</label>
              <input type="number" defaultValue={200} className="w-full px-3 py-2 border rounded-md bg-background" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Max Trades Per Day</label>
              <input type="number" defaultValue={3} className="w-full px-3 py-2 border rounded-md bg-background" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>MT5 Bridge</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Bridge URL</label>
              <input type="text" defaultValue="http://localhost:5000" className="w-full px-3 py-2 border rounded-md bg-background" />
            </div>
            <div className="p-2 text-xs bg-muted rounded-md text-muted-foreground">
              Status: Not connected
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Telegram</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Bot Token</label>
              <input type="password" className="w-full px-3 py-2 border rounded-md bg-background" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Chat ID</label>
              <input type="text" className="w-full px-3 py-2 border rounded-md bg-background" />
            </div>
            <Button variant="outline">Test Connection</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI / Ollama</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Ollama Host</label>
              <input type="text" defaultValue="http://localhost:11434" className="w-full px-3 py-2 border rounded-md bg-background" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Model</label>
              <input type="text" defaultValue="llama3.1:8b" className="w-full px-3 py-2 border rounded-md bg-background" />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
