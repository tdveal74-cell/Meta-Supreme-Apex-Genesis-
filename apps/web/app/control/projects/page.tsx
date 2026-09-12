import Link from "next/link";
import { ProjectsPanel } from "@/components/projects/ProjectsPanel";

/**
 * Projects on their own page.
 *
 * It lives here for the same reason /control/learning does: the tier shell is
 * one shared file, and a panel that can stand alone should not have to wait on
 * it. That also means this door is closed by this directory alone, with no edit
 * to ControlPlane.tsx required to make the surface reachable. Folding it into
 * Tier 1 as well is a two line change to ControlPlane's props and one line in
 * app/control/page.tsx, both written out in the staging NOTES.md.
 *
 * Projects are the scope every other read can be narrowed by, so this page sits
 * one click from the control plane rather than behind it.
 */
export default function ProjectsPage() {
  return (
    <main className="min-h-screen bg-[#04070d] text-[#e8edf2]">
      <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="mb-5 flex flex-col gap-4 rounded-2xl border border-white/10 bg-white/[0.035] px-5 py-4 backdrop-blur md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300/80">
              DEVON
            </p>
            <h1 className="mt-1 text-lg font-semibold tracking-tight text-white">Projects</h1>
            <p className="mt-1.5 max-w-xl text-xs leading-relaxed text-white/55">
              The scope the rest of the estate can be narrowed by. The knowledge routes and the
              graph route each accept a project_id and filter on it, and until this page existed
              nothing under apps/web called the projects routes at all, so that filter could only
              ever be handed a null.
            </p>
          </div>

          <nav className="flex flex-wrap items-center gap-3 text-xs text-white/55">
            <Link
              href="/control"
              className="rounded-lg border border-white/10 px-3 py-2 font-medium text-white/70 transition hover:border-white/20 hover:text-white"
            >
              Control plane
            </Link>
            <Link
              href="/command-center"
              className="rounded-lg border border-white/10 px-3 py-2 font-medium text-white/70 transition hover:border-white/20 hover:text-white"
            >
              Command Center
            </Link>
          </nav>
        </header>

        <section className="rounded-2xl border border-white/10 bg-white/[0.025] px-5 py-5 backdrop-blur">
          <ProjectsPanel />
        </section>
      </div>
    </main>
  );
}
