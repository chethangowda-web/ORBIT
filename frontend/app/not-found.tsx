import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4 text-center">
      <p className="num text-4xl font-semibold text-fg-faint">404</p>
      <h1 className="mt-2 text-lg font-semibold text-fg">Page not found</h1>
      <p className="mt-1 text-xs text-fg-muted">That page does not exist or has moved.</p>
      <Link href="/" className="mt-4 inline-flex h-8 items-center rounded-control bg-accent-strong px-3 text-[13px] font-medium text-white hover:bg-accent">
        Back to the board
      </Link>
    </main>
  );
}
