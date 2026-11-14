import { ImagePlus } from "lucide-react";

export function PhotoStatus() {
  return (
    <div className="photo-status">
      <div className="flex items-center gap-3">
        <ImagePlus aria-hidden="true" />
        <strong>Photo for your doctor</strong>
        <span className="ml-auto font-mono text-xs">Optional</span>
      </div>
      <p>No photo added. Secure photo sharing is not configured yet.</p>
    </div>
  );
}
