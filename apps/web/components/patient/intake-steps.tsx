import { Check } from "lucide-react";

export function IntakeSteps({
  step,
  complete = false,
}: {
  step: number;
  complete?: boolean;
}) {
  return (
    <nav className="intake-steps corner-marks" aria-label="Intake progress">
      <ol>
        {["Tell your story", "Follow-up questions", "Review and share"].map(
          (label, index) => (
            <li
              key={label}
              aria-current={index === step ? "step" : undefined}
              data-active={index === step}
            >
              {(index < step || complete) && <Check aria-hidden="true" />}
              <span>{label}</span>
            </li>
          ),
        )}
      </ol>
    </nav>
  );
}
