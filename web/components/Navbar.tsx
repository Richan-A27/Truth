"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/context/AuthContext";

export function Navbar() {
  const { user, loading, signOut } = useAuth();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-bg/80 backdrop-blur">
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="font-serif text-lg font-semibold text-ink">
          Truth
        </Link>

        <div className="hidden items-center gap-6 text-sm text-ink-muted sm:flex">
          <Link href="/#use-cases" className="hover:text-ink">
            Use cases
          </Link>
          <Link href="/#how-it-works" className="hover:text-ink">
            How it works
          </Link>
          <Link href="/extension" className="hover:text-ink">
            Extension
          </Link>
          <Link
            href="/verify"
            className="rounded-full border border-border px-4 py-1.5 text-ink hover:bg-bg-alt"
          >
            Try it
          </Link>
        </div>

        <div className="relative">
          {loading ? (
            <div className="h-9 w-9 rounded-full bg-bg-alt" />
          ) : user ? (
            <>
              <button
                type="button"
                onClick={() => setMenuOpen((v) => !v)}
                className="flex items-center gap-2 rounded-full border border-border py-1 pl-1 pr-3 hover:bg-bg-alt"
              >
                {user.photoURL ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={user.photoURL} alt="" className="h-7 w-7 rounded-full" />
                ) : (
                  <div className="h-7 w-7 rounded-full bg-accent-soft" />
                )}
                <span className="max-w-[8rem] truncate text-sm text-ink">
                  {user.displayName ?? user.email}
                </span>
              </button>

              {menuOpen && (
                <div
                  className="absolute right-0 top-full mt-2 w-44 overflow-hidden rounded-xl border border-border bg-surface shadow-soft-lg"
                  onMouseLeave={() => setMenuOpen(false)}
                >
                  <Link
                    href="/history"
                    onClick={() => setMenuOpen(false)}
                    className="block px-4 py-2.5 text-sm text-ink hover:bg-bg-alt"
                  >
                    History
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setMenuOpen(false);
                      signOut();
                    }}
                    className="block w-full px-4 py-2.5 text-left text-sm text-ink hover:bg-bg-alt"
                  >
                    Sign out
                  </button>
                </div>
              )}
            </>
          ) : (
            <Link
              href={`/sign-in?next=${encodeURIComponent(pathname || "/")}`}
              className="inline-flex items-center justify-center rounded-full border border-border px-4 py-2 text-sm font-medium text-ink hover:bg-bg-alt"
            >
              Sign in
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
