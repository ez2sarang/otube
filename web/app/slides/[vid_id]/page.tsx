import { Suspense } from "react";
import SlideViewerClient from "./SlideViewerClient";

export default function Page() {
  return (
    <Suspense fallback={null}>
      <SlideViewerClient />
    </Suspense>
  );
}
