import Explorer from "@/components/explorer/Explorer";
import { parseView } from "@/lib/urlState";

// The view comes from the URL so a refresh or a shared link restores it.
export default async function Home({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  return <Explorer initial={parseView(await searchParams)} />;
}
