import { motion } from "framer-motion";
import { Heart, MessageCircle, Share2, Bookmark, MoreHorizontal, ThumbsUp, Repeat2, Send } from "lucide-react";
import { cn } from "@/lib/utils";

// ────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────
type DeviceType = "mobile" | "tablet" | "web";

interface DevicePreviewProps {
  content: string;
  images: string[];
  videoUrl?: string | null;
  hashtags: string[];
  device: DeviceType;
  platformName: string;
  igPostType?: "post" | "reel";
  igMusicTrack?: string | null;
}

// ────────────────────────────────────────────────────────
// Post Content (shared across device frames)
// ────────────────────────────────────────────────────────
function PostContent({
  content,
  images,
  hashtags,
  platformName,
  compact = false,
  igMusicTrack = null,
}: {
  content: string;
  images: string[];
  hashtags: string[];
  platformName: string;
  compact?: boolean;
  igMusicTrack?: string | null;
}) {
  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-slate-900 to-slate-950 text-white overflow-y-auto custom-scrollbar">
      {/* Platform header bar */}
      <div className="sticky top-0 z-10 flex items-center justify-between px-3 py-2.5 bg-slate-900/95 backdrop-blur-sm border-b border-white/5">
        <span className={cn("font-semibold", compact ? "text-xs" : "text-sm")}>
          {platformName}
        </span>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className={cn("text-gray-400", compact ? "text-[9px]" : "text-[10px]")}>
            Preview
          </span>
        </div>
      </div>

      <div className={cn("flex-1", compact ? "p-2.5" : "p-3.5")}>
        {/* Profile header */}
        <div className="flex items-center gap-2.5 mb-3">
          <div
            className={cn(
              "rounded-full bg-gradient-to-br from-purple-500 via-pink-500 to-orange-400 flex items-center justify-center font-bold text-white flex-shrink-0",
              compact ? "w-8 h-8 text-[10px]" : "w-10 h-10 text-xs"
            )}
          >
            YB
          </div>
          <div className="flex-1 min-w-0 text-left">
            <p className={cn("font-semibold truncate", compact ? "text-xs" : "text-sm")}>
              Your Brand
            </p>
            <div className="flex flex-col">
              <p className={cn("text-gray-500 truncate", compact ? "text-[9px]" : "text-[10px]")}>
                @yourbrand &middot; Just now
              </p>
              {platformName.toLowerCase().includes("instagram") && igMusicTrack && (
                <p className={cn("text-purple-400 font-medium truncate flex items-center gap-1 mt-0.5", compact ? "text-[8px]" : "text-[9.5px]")}>
                  <svg className="w-2.5 h-2.5 flex-shrink-0 animate-pulse text-purple-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                  </svg>
                  <span className="font-semibold">{igMusicTrack.split(" – ")[0]}</span>
                  <span className="text-gray-500">&middot; {igMusicTrack.split(" – ")[1] || ""}</span>
                </p>
              )}
            </div>
          </div>
          <MoreHorizontal className={cn("text-gray-500 flex-shrink-0", compact ? "w-3.5 h-3.5" : "w-4 h-4")} />
        </div>

        {/* Post content text */}
        {content ? (
          <p
            className={cn(
              "whitespace-pre-wrap leading-relaxed mb-3 text-gray-100",
              compact ? "text-[11px]" : "text-sm"
            )}
          >
            {content}
          </p>
        ) : (
          <div className="space-y-2 mb-3">
            <div className="h-3 bg-white/5 rounded-full w-full" />
            <div className="h-3 bg-white/5 rounded-full w-4/5" />
            <div className="h-3 bg-white/5 rounded-full w-3/5" />
          </div>
        )}

        {/* Hashtags */}
        {hashtags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {hashtags.map((tag, i) => (
              <span
                key={i}
                className={cn(
                  "text-blue-400 font-medium",
                  compact ? "text-[10px]" : "text-xs"
                )}
              >
                #{tag}
              </span>
            ))}
          </div>
        )}

        {/* Images */}
        {images.length > 0 && (
          <div
            className={cn(
              "rounded-xl overflow-hidden mb-3 border border-white/5",
              images.length === 1
                ? ""
                : "grid gap-0.5",
              images.length === 2 && "grid-cols-2",
              images.length === 3 && "grid-cols-2",
              images.length >= 4 && "grid-cols-2"
            )}
          >
            {images.slice(0, 4).map((img, i) => (
              <div
                key={i}
                className={cn(
                  "relative bg-gradient-to-br from-purple-900/30 to-blue-900/30 flex items-center justify-center",
                  compact ? "min-h-[60px]" : "min-h-[80px]",
                  images.length === 1 && (compact ? "h-[120px]" : "h-[180px]"),
                  images.length === 3 && i === 0 && "row-span-2",
                  images.length >= 4 && "aspect-square"
                )}
              >
                {img.startsWith("data:") || img.startsWith("http") || img.startsWith("blob:") ? (
                  <img
                    src={img}
                    alt={`Media ${i + 1}`}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="flex flex-col items-center gap-1 text-gray-500">
                    <div className={cn("rounded-lg bg-white/5 flex items-center justify-center", compact ? "w-6 h-6" : "w-8 h-8")}>
                      <svg className={compact ? "w-3 h-3" : "w-4 h-4"} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <span className={compact ? "text-[8px]" : "text-[9px]"}>Image {i + 1}</span>
                  </div>
                )}
                {images.length > 4 && i === 3 && (
                  <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                    <span className={cn("font-bold text-white", compact ? "text-sm" : "text-lg")}>
                      +{images.length - 4}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Engagement buttons */}
        <div className="flex items-center justify-between pt-2 border-t border-white/5">
          {platformName.toLowerCase().includes("linkedin") ? (
            <>
              <EngagementBtn icon={<ThumbsUp />} label="Like" compact={compact} />
              <EngagementBtn icon={<MessageCircle />} label="Comment" compact={compact} />
              <EngagementBtn icon={<Repeat2 />} label="Repost" compact={compact} />
              <EngagementBtn icon={<Send />} label="Send" compact={compact} />
            </>
          ) : platformName.toLowerCase().includes("twitter") || platformName.toLowerCase().includes("x") ? (
            <>
              <EngagementBtn icon={<MessageCircle />} label="Reply" compact={compact} />
              <EngagementBtn icon={<Repeat2 />} label="Repost" compact={compact} />
              <EngagementBtn icon={<Heart />} label="Like" compact={compact} />
              <EngagementBtn icon={<Bookmark />} label="Save" compact={compact} />
            </>
          ) : (
            <>
              <EngagementBtn icon={<Heart />} label="Like" compact={compact} />
              <EngagementBtn icon={<MessageCircle />} label="Comment" compact={compact} />
              <EngagementBtn icon={<Share2 />} label="Share" compact={compact} />
              <EngagementBtn icon={<Bookmark />} label="Save" compact={compact} />
            </>
          )}
        </div>

        {/* Engagement counts mockup */}
        <div className="mt-2 flex items-center gap-3">
          <span className={cn("text-gray-500", compact ? "text-[9px]" : "text-[10px]")}>
            0 likes
          </span>
          <span className={cn("text-gray-500", compact ? "text-[9px]" : "text-[10px]")}>
            0 comments
          </span>
        </div>
      </div>
    </div>
  );
}

function EngagementBtn({
  icon,
  label,
  compact,
}: {
  icon: React.ReactNode;
  label: string;
  compact: boolean;
}) {
  return (
    <button className="flex items-center gap-1 text-gray-500 hover:text-purple-400 transition-colors group">
      <span className={cn("group-hover:scale-110 transition-transform", compact ? "[&>svg]:w-3 [&>svg]:h-3" : "[&>svg]:w-4 [&>svg]:h-4")}>
        {icon}
      </span>
      <span className={cn(compact ? "text-[8px]" : "text-[10px]")}>{label}</span>
    </button>
  );
}

// ────────────────────────────────────────────────────────
// Device Frames
// ────────────────────────────────────────────────────────
function MobileFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative mx-auto" style={{ width: 375, height: 812 }}>
      {/* Outer shell */}
      <div className="absolute inset-0 rounded-[50px] bg-gradient-to-b from-gray-700 to-gray-900 shadow-2xl shadow-black/60" />
      {/* Inner bezel */}
      <div className="absolute inset-[3px] rounded-[47px] bg-gradient-to-b from-gray-800 to-gray-950 border border-gray-700/50" />
      {/* Screen area */}
      <div className="absolute inset-[10px] rounded-[40px] overflow-hidden bg-black">
        {/* Notch / Dynamic Island */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 z-20">
          <div className="w-[120px] h-[32px] bg-black rounded-b-[18px] flex items-center justify-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full bg-gray-800 ring-1 ring-gray-700" />
            <div className="w-[10px] h-[10px] rounded-full bg-gray-800 ring-1 ring-gray-700" />
          </div>
        </div>
        {/* Status bar */}
        <div className="relative z-10 flex items-center justify-between px-6 pt-3 pb-1 bg-slate-900 text-white">
          <span className="text-[10px] font-semibold">9:41</span>
          <div className="flex items-center gap-1">
            <div className="flex gap-[2px]">
              {[1,2,3,4].map(i => (
                <div key={i} className="w-[3px] rounded-sm bg-white" style={{ height: 4 + i * 2 }} />
              ))}
            </div>
            <div className="w-4 h-2.5 rounded-sm border border-white ml-1 relative">
              <div className="absolute inset-[1px] bg-emerald-400 rounded-[1px]" style={{ width: '70%' }} />
            </div>
          </div>
        </div>
        {/* Content */}
        <div className="h-[calc(100%-48px)] overflow-hidden">
          {children}
        </div>
        {/* Home indicator */}
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 w-[134px] h-[5px] rounded-full bg-white/20 z-20" />
      </div>
      {/* Side buttons */}
      <div className="absolute -left-[2px] top-[120px] w-[3px] h-[30px] rounded-l-sm bg-gray-600" />
      <div className="absolute -left-[2px] top-[170px] w-[3px] h-[55px] rounded-l-sm bg-gray-600" />
      <div className="absolute -left-[2px] top-[235px] w-[3px] h-[55px] rounded-l-sm bg-gray-600" />
      <div className="absolute -right-[2px] top-[170px] w-[3px] h-[70px] rounded-r-sm bg-gray-600" />
    </div>
  );
}

function TabletFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative mx-auto" style={{ width: 768, height: 570 }}>
      {/* Outer shell */}
      <div className="absolute inset-0 rounded-[24px] bg-gradient-to-b from-gray-700 to-gray-900 shadow-2xl shadow-black/60" />
      {/* Inner bezel */}
      <div className="absolute inset-[2px] rounded-[22px] bg-gradient-to-b from-gray-800 to-gray-950 border border-gray-700/50" />
      {/* Screen */}
      <div className="absolute inset-[8px] rounded-[16px] overflow-hidden bg-black">
        {/* Camera dot */}
        <div className="absolute top-3 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-gray-800 ring-1 ring-gray-700 z-20" />
        {/* Status bar */}
        <div className="relative z-10 flex items-center justify-between px-6 pt-2 pb-1 bg-slate-900 text-white">
          <span className="text-[10px] font-semibold">9:41</span>
          <div className="flex items-center gap-1">
            <div className="flex gap-[2px]">
              {[1,2,3,4].map(i => (
                <div key={i} className="w-[3px] rounded-sm bg-white" style={{ height: 4 + i * 2 }} />
              ))}
            </div>
            <div className="w-4 h-2.5 rounded-sm border border-white ml-1 relative">
              <div className="absolute inset-[1px] bg-emerald-400 rounded-[1px]" style={{ width: '70%' }} />
            </div>
          </div>
        </div>
        {/* Content */}
        <div className="h-[calc(100%-32px)] overflow-hidden">
          {children}
        </div>
      </div>
    </div>
  );
}

function WebFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative mx-auto" style={{ width: "100%", maxWidth: 960, height: 560 }}>
      {/* Window shadow */}
      <div className="absolute inset-0 rounded-2xl shadow-2xl shadow-black/50" />
      {/* Browser chrome */}
      <div className="absolute inset-0 rounded-2xl overflow-hidden border border-gray-700/50 bg-gray-900 flex flex-col">
        {/* Title bar */}
        <div className="flex items-center gap-3 px-4 py-2.5 bg-gray-800/90 border-b border-gray-700/50">
          {/* Traffic lights */}
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/80 border border-red-600/50" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80 border border-yellow-600/50" />
            <div className="w-3 h-3 rounded-full bg-green-500/80 border border-green-600/50" />
          </div>
          {/* URL bar */}
          <div className="flex-1 flex items-center justify-center">
            <div className="flex items-center gap-2 bg-gray-900/60 rounded-lg px-3 py-1 max-w-md w-full border border-gray-700/30">
              <svg className="w-3 h-3 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
              <span className="text-[11px] text-gray-400 truncate">
                app.yourbrand.com/feed
              </span>
            </div>
          </div>
          {/* Window controls placeholder */}
          <div className="w-[52px]" />
        </div>
        {/* Tab bar */}
        <div className="flex items-center px-4 py-1 bg-gray-850 border-b border-gray-700/30 bg-gray-800/50">
          <div className="flex items-center gap-1.5 bg-gray-900/50 rounded-t-lg px-3 py-1 border border-gray-700/30 border-b-0">
            <div className="w-3 h-3 rounded-full bg-gradient-to-br from-purple-500 to-blue-500" />
            <span className="text-[10px] text-gray-300">Your Brand - Feed</span>
            <button className="ml-2 text-gray-500 hover:text-white">
              <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
        {/* Content */}
        <div className="flex-1 overflow-hidden">
          <div className="h-full flex">
            {/* Sidebar mock */}
            <div className="w-[200px] bg-slate-900/50 border-r border-white/5 p-3 hidden lg:block">
              <div className="space-y-3">
                <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-purple-500/10 border border-purple-500/20">
                  <div className="w-4 h-4 rounded bg-purple-500/30" />
                  <span className="text-[10px] text-purple-300">Feed</span>
                </div>
                {["Explore", "Messages", "Notifications", "Profile"].map((item) => (
                  <div key={item} className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-white/5">
                    <div className="w-4 h-4 rounded bg-white/10" />
                    <span className="text-[10px] text-gray-500">{item}</span>
                  </div>
                ))}
              </div>
            </div>
            {/* Main feed */}
            <div className="flex-1 overflow-hidden max-w-[560px] mx-auto">
              {children}
            </div>
            {/* Right sidebar mock */}
            <div className="w-[180px] bg-slate-900/30 border-l border-white/5 p-3 hidden xl:block">
              <div className="text-[10px] text-gray-500 font-medium mb-2">Trending</div>
              {[1,2,3].map(i => (
                <div key={i} className="mb-2">
                  <div className="h-2 bg-white/5 rounded w-3/4 mb-1" />
                  <div className="h-2 bg-white/5 rounded w-1/2" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ReelPreviewContent({
  content,
  videoUrl,
  imageUrl,
  hashtags,
  igMusicTrack,
  compact = false,
}: {
  content: string;
  videoUrl?: string;
  imageUrl?: string;
  hashtags: string[];
  igMusicTrack?: string | null;
  compact?: boolean;
}) {
  return (
    <div className="relative flex flex-col h-full bg-black text-white overflow-hidden select-none">
      {/* Inline styles for the marquee */}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes reelMarquee {
          0% { transform: translateX(100%); }
          100% { transform: translateX(-100%); }
        }
        .reel-marquee {
          display: inline-block;
          white-space: nowrap;
          animation: reelMarquee 15s linear infinite;
        }
      `}} />

      {/* Video or Image Background */}
      <div className="absolute inset-0 z-0 bg-gradient-to-b from-slate-900 via-black to-slate-950 flex items-center justify-center">
        {videoUrl ? (
          <video
            src={videoUrl}
            className="w-full h-full object-cover"
            autoPlay
            loop
            muted
            playsInline
          />
        ) : imageUrl ? (
          <img
            src={imageUrl}
            alt="Reel Media fallback"
            className="w-full h-full object-cover opacity-80"
          />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-pink-900/40 via-purple-900/40 to-blue-900/40 flex flex-col items-center justify-center p-6 text-center text-gray-500">
            <svg className="w-12 h-12 mb-3 text-pink-500/50 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
            </svg>
            <span className="text-xs text-gray-400">Reel Video Preview</span>
            <span className="text-[10px] text-gray-600 mt-1">Upload a video or choose an image to view here</span>
          </div>
        )}
      </div>

      {/* Dark overlay at bottom for text readability */}
      <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/85 via-black/45 to-transparent z-10 pointer-events-none" />

      {/* Engagement Buttons stacked vertically on the right */}
      <div className="absolute right-3 bottom-20 z-20 flex flex-col items-center gap-4">
        <div className="flex flex-col items-center">
          <button className="w-10 h-10 rounded-full bg-black/40 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:text-pink-500 transition-colors">
            <Heart className="w-5 h-5" />
          </button>
          <span className="text-[10px] text-white/90 mt-1 font-medium shadow-sm">1.2K</span>
        </div>

        <div className="flex flex-col items-center">
          <button className="w-10 h-10 rounded-full bg-black/40 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:text-purple-400 transition-colors">
            <MessageCircle className="w-5 h-5" />
          </button>
          <span className="text-[10px] text-white/90 mt-1 font-medium shadow-sm">45</span>
        </div>

        <div className="flex flex-col items-center">
          <button className="w-10 h-10 rounded-full bg-black/40 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:text-blue-400 transition-colors">
            <Send className="w-5 h-5" />
          </button>
          <span className="text-[10px] text-white/90 mt-1 font-medium shadow-sm">12</span>
        </div>

        <div className="flex flex-col items-center">
          <button className="w-10 h-10 rounded-full bg-black/40 backdrop-blur-md border border-white/10 flex items-center justify-center text-white hover:text-amber-400 transition-colors">
            <Bookmark className="w-5 h-5" />
          </button>
          <span className="text-[10px] text-white/90 mt-1 font-medium shadow-sm">89</span>
        </div>

        {/* Spinning Record Icon for Music */}
        <div className="w-8 h-8 rounded-full border border-white/20 bg-gradient-to-r from-purple-600 to-pink-600 flex items-center justify-center animate-spin" style={{ animationDuration: '4s' }}>
          <div className="w-3 h-3 rounded-full bg-black border border-white/10" />
        </div>
      </div>

      {/* Overlay details at the bottom left */}
      <div className="absolute left-3 right-16 bottom-6 z-20 space-y-2.5 text-left">
        {/* Profile */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-500 to-pink-500 flex items-center justify-center font-bold text-white border border-white/20">
            YB
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-semibold text-white truncate shadow-sm">@yourbrand</span>
              <span className="px-1.5 py-0.5 rounded bg-white/25 text-[8px] font-bold text-white tracking-wide uppercase">Follow</span>
            </div>
          </div>
        </div>

        {/* Content text & hashtags */}
        <div className="max-h-24 overflow-y-auto pr-1">
          <p className="text-[11px] leading-relaxed text-white/95 font-medium shadow-sm whitespace-pre-wrap">
            {content || "Describe your Reel video here..."}
          </p>
          {hashtags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {hashtags.map((tag, i) => (
                <span key={i} className="text-blue-300 font-semibold text-[10px] hover:underline shadow-sm">
                  #{tag}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Music Display at the bottom */}
        <div className="flex items-center gap-2 pt-1 border-t border-white/10 w-full overflow-hidden">
          <div className="w-5 h-5 rounded-full bg-black/40 flex items-center justify-center flex-shrink-0">
            <svg className="w-3 h-3 text-purple-300 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
            </svg>
          </div>
          <div className="flex-1 overflow-hidden min-w-0">
            <div className="reel-marquee text-[10px] text-purple-200 font-semibold tracking-wide">
              {igMusicTrack ? `♫ ${igMusicTrack}` : "♫ Original Audio"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────
// Main DevicePreview Component
// ────────────────────────────────────────────────────────
export default function DevicePreview({
  content,
  images,
  videoUrl = null,
  hashtags,
  device,
  platformName,
  igPostType,
  igMusicTrack,
}: DevicePreviewProps) {
  const isReel = platformName.toLowerCase().includes("instagram") && igPostType === "reel";

  const postContent = isReel ? (
    <ReelPreviewContent
      content={content}
      videoUrl={videoUrl || undefined}
      imageUrl={images[0] || undefined}
      hashtags={hashtags}
      igMusicTrack={igMusicTrack}
      compact={device === "mobile"}
    />
  ) : (
    <PostContent
      content={content}
      images={images}
      hashtags={hashtags}
      platformName={platformName}
      compact={device === "mobile"}
      igMusicTrack={igMusicTrack}
    />
  );

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="flex items-center justify-center"
    >
      {device === "mobile" && (
        <div className="transform scale-[0.65] origin-top">
          <MobileFrame>{postContent}</MobileFrame>
        </div>
      )}

      {device === "tablet" && (
        <div className="transform scale-[0.75] origin-top">
          <TabletFrame>{postContent}</TabletFrame>
        </div>
      )}

      {device === "web" && (
        <div className="w-full">
          <WebFrame>{postContent}</WebFrame>
        </div>
      )}
    </motion.div>
  );
}
