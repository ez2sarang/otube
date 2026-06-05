import { Suspense } from "react";
import HistoryPageClient from "./HistoryPageClient";

export default function Page() {
  return (
    <Suspense fallback={null}>
      <HistoryPageClient />
    </Suspense>
  );
}
