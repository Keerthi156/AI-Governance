import { Suspense } from "react";

import LoginClient from "./LoginClient";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-md py-24">
          <LoadingSkeleton rows={4} />
        </div>
      }
    >
      <LoginClient />
    </Suspense>
  );
}
