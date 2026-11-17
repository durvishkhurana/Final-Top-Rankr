"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ErrorNote } from "@/components/state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { post } from "@/lib/api";

const FIELDS = {
  login: [
    ["email", "Email", "email", "email"],
    ["password", "Password", "password", "current-password"],
  ],
  signup: [
    ["name", "Name", "text", "name"],
    ["email", "Email", "email", "email"],
    ["password", "Password (at least 8 characters)", "password", "new-password"],
    ["country", "Country (optional)", "text", "country-name"],
    ["institution", "Institution (optional)", "text", "organization"],
  ],
} as const;

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await post(`/auth/${mode}`, Object.fromEntries(new FormData(e.currentTarget)));
      await queryClient.invalidateQueries();
      router.push("/problems");
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  return (
    <Card className="mx-auto mt-8 max-w-sm">
      <CardHeader>
        <CardTitle>{mode === "login" ? "Sign in" : "Create an account"}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="space-y-4">
          {FIELDS[mode].map(([name, label, type, autoComplete]) => (
            <div key={name} className="space-y-1.5">
              <Label htmlFor={name}>{label}</Label>
              <Input
                id={name}
                name={name}
                type={type}
                autoComplete={autoComplete}
                required={!label.includes("optional")}
                minLength={mode === "signup" && name === "password" ? 8 : undefined}
              />
            </div>
          ))}
          {error != null && <ErrorNote error={error} />}
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>
        <p className="mt-4 text-sm text-muted-foreground">
          {mode === "login" ? (
            <>
              <Link href="/forgot-password" className="text-foreground underline">
                Forgot your password?
              </Link>
              <br />
              No account?{" "}
              <Link href="/signup" className="text-foreground underline">
                Create one
              </Link>
            </>
          ) : (
            <>
              Already registered?{" "}
              <Link href="/login" className="text-foreground underline">
                Sign in
              </Link>
            </>
          )}
        </p>
      </CardContent>
    </Card>
  );
}
