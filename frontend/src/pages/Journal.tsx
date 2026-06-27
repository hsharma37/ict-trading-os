import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'

export default function Journal() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Journal</h1>
        <p className="text-muted-foreground">Review and grade your trades</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Pre-Trade Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <textarea
              className="w-full px-3 py-2 border rounded-md bg-background min-h-[150px]"
              placeholder="Enter your pre-trade analysis..."
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Self-Grade</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {['Setup', 'Execution', 'Management'].map((grade) => (
              <div key={grade} className="space-y-2">
                <label className="text-sm font-medium">{grade} (1-10)</label>
                <input type="range" min="1" max="10" className="w-full" />
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Post-Trade Notes</CardTitle>
          </CardHeader>
          <CardContent>
            <textarea
              className="w-full px-3 py-2 border rounded-md bg-background min-h-[150px]"
              placeholder="What went well? What would you change?"
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Lessons</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <textarea
            className="w-full px-3 py-2 border rounded-md bg-background min-h-[100px]"
            placeholder="Key lessons from this trade..."
          />
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Add tag..."
              className="flex-1 px-3 py-2 border rounded-md bg-background"
            />
            <Button>Add Tag</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
