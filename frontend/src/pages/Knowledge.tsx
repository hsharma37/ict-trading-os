import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'

export default function Knowledge() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Knowledge Base</h1>
        <p className="text-muted-foreground">ICT transcripts, notes, and AI chat</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Sources</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">YouTube URL</label>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Paste YouTube link..."
                  className="flex-1 px-3 py-2 border rounded-md bg-background"
                />
                <Button>Add</Button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Or paste transcript text</label>
              <textarea
                className="w-full px-3 py-2 border rounded-md bg-background min-h-[100px]"
                placeholder="Paste transcript here..."
              />
              <Button className="w-full">Add to Knowledge Base</Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI Chat</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="h-[300px] border rounded-md bg-muted p-4 overflow-y-auto">
              <div className="text-sm text-muted-foreground text-center mt-20">
                Ask questions about ICT concepts, setups, or your knowledge base
              </div>
            </div>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Ask a question..."
                className="flex-1 px-3 py-2 border rounded-md bg-background"
              />
              <Button>Send</Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Search</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Search your knowledge base..."
              className="flex-1 px-3 py-2 border rounded-md bg-background"
            />
            <Button>Search</Button>
          </div>
          <div className="mt-4 text-sm text-muted-foreground">
            Search results will appear here
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
