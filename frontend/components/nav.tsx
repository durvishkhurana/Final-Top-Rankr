"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Button, buttonVariants } from "@/components/ui/button";
import { post } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { cn } from "@/lib/utils";

const LINKS = [
  ["/problems", "Problems"],
  ["/contests", "Contests"],
  ["/leaderboard", "Leaderboard"],
  ["/statistics", "Statistics"],
  ["/research", "Research"],
] as const;

export function Nav() {
  const me = useMe();
  const pathname = usePathname();
  const router = useRouter();
  const queryClient = useQueryClient();

  async function logout() {
    await post("/auth/logout");
    queryClient.clear();
    router.push("/");
  }

  return (
    <header className="border-b bg-background">
      <nav
        aria-label="Main"
        className="mx-auto flex w-full max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3"
      >
        <Link href="/" className="text-lg font-semibold tracking-tight">
          TopRanker
        </Link>
        <div className="flex gap-4 text-sm">
          {LINKS.map(([href, label]) => (
            <Link
              key={href}
              href={href}
              aria-current={pathname.startsWith(href) ? "page" : undefined}
              className={cn(
                "text-muted-foreground hover:text-foreground",
                pathname.startsWith(href) && "font-medium text-foreground",
              )}
            >
              {label}
            </Link>
          ))}
          {me && (
            <>
              <Link href="/courses" className="text-muted-foreground hover:text-foreground">
                Courses
              </Link>
              <Link href="/tests" className="text-muted-foreground hover:text-foreground">
                Tests
              </Link>
              <Link href="/contribute" className="text-muted-foreground hover:text-foreground">
                Contribute
              </Link>
            </>
          )}
          {me?.role === "admin" && (
            <Link href="/admin" className="text-muted-foreground hover:text-foreground">
              Admin
            </Link>
          )}
        </div>
        <div className="ml-auto flex items-center gap-2 text-sm">
          {me === undefined ? null : me ? (
            <>
              <Link href={`/profile/${me.id}`} className="font-medium hover:underline">
                {me.name}
              </Link>
              <Button variant="outline" size="sm" onClick={logout}>
                Sign out
              </Button>
            </>
          ) : (
            <>
              <Link href="/login" className={buttonVariants({ variant: "ghost", size: "sm" })}>
                Sign in
              </Link>
              <Link href="/signup" className={buttonVariants({ size: "sm" })}>
                Create account
              </Link>
            </>
          )}
        </div>
      </nav>
    </header>
  );
}
