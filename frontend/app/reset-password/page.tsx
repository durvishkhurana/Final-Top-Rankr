import { Suspense } from "react";

import { ResetPasswordForm } from "@/components/account-forms";

export const metadata = { title: "New password" };

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}
