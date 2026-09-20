export function Card({ children, className = "" }) {
  return (
    <div className={`bg-base-800 border border-base-700 rounded-lg ${className}`}>
      {children}
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, action }) {
  return (
    <div className="flex items-start justify-between gap-6 mb-8">
      <div>
        {eyebrow && (
          <p className="font-mono text-[11px] uppercase tracking-wider text-signal-cyan mb-1.5">
            {eyebrow}
          </p>
        )}
        <h1 className="font-display text-2xl font-semibold text-base-100 tracking-tight">
          {title}
        </h1>
        {description && <p className="text-sm text-base-400 mt-1.5 max-w-xl">{description}</p>}
      </div>
      {action}
    </div>
  );
}
