interface Props {
  src: string | null;
  name: string;
  size?: number;
  online?: boolean;
}

export function Avatar({ src, name, size = 48, online }: Props) {
  const initials = name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      {src ? (
        <img
          src={src}
          alt={name}
          className="w-full h-full rounded-full object-cover"
        />
      ) : (
        <div
          className="w-full h-full rounded-full flex items-center justify-center text-white font-semibold"
          style={{
            background: `linear-gradient(135deg, #6C5CE7, #A29BFE)`,
            fontSize: size * 0.35,
          }}
        >
          {initials || '?'}
        </div>
      )}
      {online !== undefined && (
        <span
          className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-[var(--nexly-surface)] ${
            online ? 'bg-[var(--nexly-online)]' : 'bg-gray-400'
          }`}
        />
      )}
    </div>
  );
}
