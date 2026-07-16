import { cn } from "@/lib/utils";

type Platform =
  | "facebook"
  | "instagram"
  | "linkedin"
  | "twitter"
  | "youtube"
  | "tiktok"
  | "pinterest";

interface PlatformIconProps {
  platform: Platform;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
  className?: string;
}

const platformConfig: Record<
  Platform,
  { label: string; color: string; bg: string; letter: string }
> = {
  facebook: {
    label: "Facebook",
    color: "#1877F2",
    bg: "bg-[#1877F2]",
    letter: "f",
  },
  instagram: {
    label: "Instagram",
    color: "#E4405F",
    bg: "bg-gradient-to-br from-[#F58529] via-[#DD2A7B] to-[#8134AF]",
    letter: "IG",
  },
  linkedin: {
    label: "LinkedIn",
    color: "#0A66C2",
    bg: "bg-[#0A66C2]",
    letter: "in",
  },
  twitter: {
    label: "X / Twitter",
    color: "#1DA1F2",
    bg: "bg-[#000000]",
    letter: "X",
  },
  youtube: {
    label: "YouTube",
    color: "#FF0000",
    bg: "bg-[#FF0000]",
    letter: "YT",
  },
  tiktok: {
    label: "TikTok",
    color: "#000000",
    bg: "bg-[#000000]",
    letter: "TT",
  },
  pinterest: {
    label: "Pinterest",
    color: "#BD081C",
    bg: "bg-[#BD081C]",
    letter: "P",
  },
};

const sizeMap = {
  sm: { container: "h-6 w-6", text: "text-[9px]", label: "text-xs" },
  md: { container: "h-8 w-8", text: "text-[11px]", label: "text-sm" },
  lg: { container: "h-10 w-10", text: "text-sm", label: "text-base" },
};

// SVG icons per platform
function PlatformSVG({ platform, size }: { platform: Platform; size: number }) {
  switch (platform) {
    case "facebook":
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="white">
          <path d="M9.198 21.5h4v-8.01h3.604l.396-3.98h-4V7.5a1 1 0 011-1h3v-4h-3a5 5 0 00-5 5v2.01h-2l-.396 3.98h2.396v8.01z" />
        </svg>
      );
    case "instagram":
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="white">
          <path d="M12 2c2.717 0 3.056.01 4.122.06 1.065.05 1.79.217 2.428.465.66.254 1.216.598 1.772 1.153a4.908 4.908 0 011.153 1.772c.247.637.415 1.363.465 2.428.047 1.066.06 1.405.06 4.122 0 2.717-.01 3.056-.06 4.122-.05 1.065-.218 1.79-.465 2.428a4.883 4.883 0 01-1.153 1.772 4.915 4.915 0 01-1.772 1.153c-.637.247-1.363.415-2.428.465-1.066.047-1.405.06-4.122.06-2.717 0-3.056-.01-4.122-.06-1.065-.05-1.79-.218-2.428-.465a4.89 4.89 0 01-1.772-1.153 4.904 4.904 0 01-1.153-1.772c-.248-.637-.415-1.363-.465-2.428C2.013 15.056 2 14.717 2 12c0-2.717.01-3.056.06-4.122.05-1.066.217-1.79.465-2.428a4.88 4.88 0 011.153-1.772A4.897 4.897 0 015.45 2.525c.638-.248 1.362-.415 2.428-.465C8.944 2.013 9.283 2 12 2zm0 5a5 5 0 100 10 5 5 0 000-10zm0 2a3 3 0 110 6 3 3 0 010-6zm5.25-3.5a1.25 1.25 0 100 2.5 1.25 1.25 0 000-2.5z" />
        </svg>
      );
    case "linkedin":
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="white">
          <path d="M6.94 5a2 2 0 11-4-.002 2 2 0 014 .002zM7 8.48H3V21h4V8.48zm6.32 0H9.34V21h3.94v-6.57c0-3.66 4.77-4 4.77 0V21H22v-7.93c0-6.17-7.06-5.94-8.72-2.91l.04-1.68z" />
        </svg>
      );
    case "twitter":
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="white">
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
        </svg>
      );
    case "youtube":
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="white">
          <path d="M23.498 6.186a3.016 3.016 0 00-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 00.502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 002.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 002.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
        </svg>
      );
    case "tiktok":
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="white">
          <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.3 0 .59.05.86.12V9.01a6.27 6.27 0 00-.86-.06 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.34-6.34V8.55a8.19 8.19 0 004.76 1.52V6.69h-1z" />
        </svg>
      );
    case "pinterest":
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="white">
          <path d="M12 0a12 12 0 00-4.373 23.178c-.07-.633-.134-1.606.028-2.298.146-.625.943-3.998.943-3.998s-.24-.482-.24-1.194c0-1.118.648-1.953 1.456-1.953.687 0 1.018.515 1.018 1.134 0 .69-.44 1.723-.667 2.68-.19.803.402 1.457 1.193 1.457 1.43 0 2.53-1.51 2.53-3.69 0-1.929-1.387-3.278-3.369-3.278-2.294 0-3.64 1.72-3.64 3.5 0 .693.267 1.435.6 1.838a.24.24 0 01.056.23c-.061.256-.198.803-.224.915-.035.146-.116.177-.268.107-1-.465-1.624-1.926-1.624-3.1 0-2.523 1.834-4.84 5.286-4.84 2.775 0 4.932 1.977 4.932 4.62 0 2.757-1.739 4.976-4.151 4.976-.811 0-1.573-.421-1.834-.919l-.498 1.902c-.181.695-.669 1.566-.995 2.097A12 12 0 1012 0z" />
        </svg>
      );
    default:
      return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="white">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.53c-.26-.81-1-1.4-1.9-1.4h-1v-3c0-.55-.45-1-1-1h-6v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.4z" />
        </svg>
      );
  }
}

export default function PlatformIcon({
  platform,
  size = "md",
  showLabel = false,
  className,
}: PlatformIconProps) {
  // Normalize platform key/name/slug
  const platformKey = (
    typeof platform === "string"
      ? platform
      : typeof platform === "object" && platform
      ? (platform as any).slug || (platform as any).name || ""
      : ""
  ).toLowerCase() as Platform;

  const config = platformConfig[platformKey] || {
    label: typeof platform === "string" ? platform : (platform as any)?.name || "Social Profile",
    color: "#64748B",
    bg: "bg-slate-600",
    letter: "S",
  };

  const sizes = sizeMap[size] || sizeMap.md;
  const iconSize = size === "sm" ? 12 : size === "md" ? 14 : 18;

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div
        className={cn(
          "flex shrink-0 items-center justify-center rounded-lg",
          sizes.container,
          config.bg
        )}
      >
        <PlatformSVG platform={platformKey} size={iconSize} />
      </div>
      {showLabel && (
        <span className={cn("font-medium text-slate-300", sizes.label)}>
          {config.label}
        </span>
      )}
    </div>
  );
}
