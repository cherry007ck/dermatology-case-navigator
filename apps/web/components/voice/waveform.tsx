export function Waveform({ active = false }: { active?: boolean }) {
  return (
    <div className="waveform" data-active={active} aria-hidden="true">
      {Array.from({ length: 49 }, (_, i) => {
        const height = Math.round(
          5 +
            Math.pow(Math.sin(i * 0.39), 2) *
              (18 + 36 * Math.pow(Math.sin(i * 0.12), 2)),
        );
        return (
          <span key={i} style={{ height, animationDelay: `${i * 35}ms` }} />
        );
      })}
    </div>
  );
}
