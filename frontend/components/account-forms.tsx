"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect } from "react";

import { ErrorNote } from "@/components/state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { post } from "@/lib/api";
import { useMe } from "@/lib/auth";

function Shell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card className="mx-auto mt-8 max-w-sm">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">{children}</CardContent>
    </Card>
  );
}

function SignInLink() {
  return (
    <Link href="/login" className="underline">
      Sign in
    </Link>
  );
}

export function ForgotPasswordForm() {
  const send = useMutation({ mutationFn: (email: string) => post("/auth/password/forgot", { email }) });
  return (
    <Shell title="Reset your password">
      {send.isSuccess ? (
        <p role="status">
          If an account exists for that address, an email with a reset link is on its way. The link works for one hour.
        </p>
      ) : (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            send.mutate(String(new FormData(e.currentTarget).get("email")));
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" name="email" type="email" autoComplete="email" required />
          </div>
          {send.error && <ErrorNote error={send.error} />}
          <Button type="submit" disabled={send.isPending} className="w-full">
            Send reset link
          </Button>
        </form>
      )}
      <p className="text-muted-foreground">
        Remembered it? <SignInLink />
      </p>
    </Shell>
  );
}

export function ResetPasswordForm() {
  const token = useSearchParams().get("token") ?? "";
  const reset = useMutation({
    mutationFn: (password: string) => post("/auth/password/reset", { token, password }),
  });
  return (
    <Shell title="Choose a new password">
      {reset.isSuccess ? (
        <p role="status">
          Your password has been changed and you have been signed out everywhere. <SignInLink /> with the new password.
        </p>
      ) : (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            reset.mutate(String(new FormData(e.currentTarget).get("password")));
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="password">New password (at least 8 characters)</Label>
            <Input id="password" name="password" type="password" autoComplete="new-password" minLength={8} required />
          </div>
          {reset.error && <ErrorNote error={reset.error} />}
          <Button type="submit" disabled={reset.isPending || !token} className="w-full">
            Set password
          </Button>
        </form>
      )}
    </Shell>
  );
}

export function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const queryClient = useQueryClient();
  const { mutate, isSuccess, error } = useMutation({
    mutationFn: () => post("/auth/verify", { token }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["me"] }),
  });
  useEffect(() => mutate(), [mutate]);
  return (
    <Shell title="Confirm your email">
      {isSuccess ? (
        <p role="status">
          Thank you, your email address is confirmed.{" "}
          <Link href="/problems" className="underline">
            Go to the problems
          </Link>
        </p>
      ) : error ? (
        <ErrorNote error={error} />
      ) : (
        <p role="status">Checking the link…</p>
      )}
    </Shell>
  );
}

/** Shown under the navigation bar until the signed-in user confirms their email. */
export function VerifyBanner() {
  const me = useMe();
  const resend = useMutation({ mutationFn: () => post("/auth/verify/resend") });
  if (!me || me.email_verified) return null;
  return (
    <div className="border-b bg-muted/50 text-sm">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-2">
        <span>
          Please confirm your email address <strong>{me.email}</strong> with the link we sent you.
        </span>
        {resend.isSuccess ? (
          <span className="text-muted-foreground">Sent again.</span>
        ) : (
          <Button variant="outline" size="sm" disabled={resend.isPending} onClick={() => resend.mutate()}>
            Send the link again
          </Button>
        )}
        {resend.error && <span className="text-destructive">{resend.error.message}</span>}
      </div>
    </div>
  );
}
