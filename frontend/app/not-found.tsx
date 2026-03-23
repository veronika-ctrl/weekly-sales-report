import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 px-4">
      <h1 className="text-2xl font-semibold text-foreground">Page not found</h1>
      <p className="text-sm text-muted-foreground text-center max-w-md">
        The page you’re looking for doesn’t exist or the app is still compiling. Try opening the main report.
      </p>
      <Link
        href="/summary"
        className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        Go to Summary
      </Link>
      <Link href="/settings" className="text-sm text-muted-foreground hover:text-foreground underline">
        Settings
      </Link>
    </div>
  )
}
