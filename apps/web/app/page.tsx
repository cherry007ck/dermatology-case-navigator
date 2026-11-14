import { Stethoscope } from "lucide-react";
import Image from "next/image";

import { DoctorEntryButton, PatientEntryButton } from "@/components/home/home-entry-actions";

// Homepage only. Every class here is local to this page, so the intake and doctor
// screens keep their current look and behaviour.
//
// Layout reflows by available width (which also covers browser zoom):
// - below 48rem: one column (headline, stethoscope, Patient, Doctor);
// - 48rem to 72rem: headline, stethoscope row, then Patient | Doctor;
// - 72rem and wider: the four-column grid (Patient | stethoscope × 2 | Doctor).
// No fixed heights: every row grows with its content.

// Hero artwork. To use the corrected PNG, place it in apps/web/public/home/ and
// update these three values to its file name and pixel size.
const HERO_SRC = "/home/stethoscope.svg";
const HERO_WIDTH = 640;
const HERO_HEIGHT = 460;

const RULE = "border-[#d9dde2]";

/** Small navy square on a grid line at the frame edge. Decorative. */
function Marker({ className }: { className: string }) {
  return <span aria-hidden="true" className={`absolute size-1.5 bg-[#1f4e8c] ${className}`} />;
}

function EntryLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-center gap-2 font-mono text-sm tracking-[0.08em] text-[#111418] uppercase">
      <span aria-hidden="true" className="size-2.5 shrink-0 bg-[#1f4e8c]" />
      {children}
    </p>
  );
}

function Entry({
  id,
  label,
  title,
  text,
  action,
  className,
}: {
  id: string;
  label: string;
  title: string;
  text: string;
  action: React.ReactNode;
  className: string;
}) {
  return (
    <section aria-labelledby={id} className={`flex min-w-0 flex-col gap-4 p-6 sm:p-8 ${className}`}>
      <EntryLabel>{label}</EntryLabel>
      <h2
        id={id}
        className="text-[1.75rem] leading-tight font-medium break-words min-[72rem]:min-h-[2lh] min-[72rem]:text-[clamp(1.625rem,2.1vw,2rem)]"
      >
        {title}
      </h2>
      <p className="text-lg leading-snug break-words min-[72rem]:min-h-[2lh]">{text}</p>
      <div className="pt-2">{action}</div>
    </section>
  );
}

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-[1280px] px-3 py-4 sm:px-6 sm:py-6" data-testid="home">
      <div className={`relative border ${RULE} bg-[#f6f7f8] text-[#111418]`}>
        <header className={`flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b ${RULE} px-4 py-3 sm:px-6 sm:py-4`}>
          <div className="flex items-center gap-3">
            <Stethoscope aria-hidden="true" className="size-7 shrink-0 text-[#1f4e8c]" strokeWidth={1.5} />
            <span aria-hidden="true" className="h-6 w-px bg-[#c9ced4]" />
            <span className="text-lg font-semibold">Exasol.sh</span>
          </div>
          <p className="font-mono text-xs tracking-[0.12em] uppercase sm:text-sm">Exasol hackathon project</p>
        </header>

        <div className="relative">
          {/* Four continuous column rules through the headline and the entry row (wide layout only). */}
          <div aria-hidden="true" className="pointer-events-none absolute inset-0 hidden min-[72rem]:block">
            {["left-1/4", "left-1/2", "left-3/4"].map((pos) => (
              <span key={pos} className={`absolute inset-y-0 w-px bg-[#d9dde2] ${pos}`} />
            ))}
          </div>

          <section
            className={`relative border-b ${RULE} px-5 pt-10 pb-8 text-center sm:px-8 sm:pt-12 min-[72rem]:pt-14 min-[72rem]:pb-28`}
          >
            <Marker className="top-3 -left-[3.5px]" />
            <Marker className="top-3 -right-[3.5px]" />
            <h1 className="relative mx-auto max-w-4xl text-[clamp(1.75rem,1rem+3.6vw,3.5rem)] leading-tight font-medium tracking-tight break-words">
              Every story deserves a closer look.
            </h1>
          </section>

          <div className="relative grid md:grid-cols-2 min-[72rem]:grid-cols-4">
            <Marker className="-top-[3.5px] -left-[3.5px]" />
            <Marker className="-top-[3.5px] -right-[3.5px]" />

            {/* The artwork rises into the headline row by exactly that row's bottom padding,
                so it can never cover the headline text. */}
            <div
              className={`flex min-w-0 items-center justify-center border-b ${RULE} px-6 py-6 md:col-span-2 min-[72rem]:col-span-2 min-[72rem]:col-start-2 min-[72rem]:row-start-1 min-[72rem]:-mt-28 min-[72rem]:border-b-0 min-[72rem]:px-4 min-[72rem]:py-0 min-[72rem]:pb-6`}
            >
              <Image
                src={HERO_SRC}
                alt=""
                width={HERO_WIDTH}
                height={HERO_HEIGHT}
                priority
                unoptimized
                className="h-auto w-full max-w-[240px] sm:max-w-[360px] md:max-w-[440px] min-[72rem]:max-w-none"
              />
            </div>

            <Entry
              id="home-patient-title"
              label="Patient"
              title="Tell your story"
              text="Share your skin concern with your doctor."
              action={<PatientEntryButton />}
              className={`md:border-r ${RULE} min-[72rem]:col-start-1 min-[72rem]:row-start-1 min-[72rem]:border-r-0`}
            />

            <Entry
              id="home-doctor-title"
              label="Doctor"
              title="Review a consultation"
              text="Read the patient brief and explore published cases."
              action={<DoctorEntryButton />}
              className={`border-t ${RULE} md:border-t-0 min-[72rem]:col-start-4 min-[72rem]:row-start-1`}
            />

            <Marker className="bottom-3 -left-[3.5px]" />
            <Marker className="bottom-3 -right-[3.5px]" />
          </div>
        </div>
      </div>
    </main>
  );
}
