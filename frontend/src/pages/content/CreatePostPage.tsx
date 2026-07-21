import { useState, useRef, useCallback, useEffect, type ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Upload,
  X,
  Hash,
  Image as ImageIcon,
  Camera,
  Wand2,
  Check,
  Plus,
  CalendarDays,
  Rocket,
  ArrowRight,
  ArrowLeft,
  Monitor,
  Tablet,
  Smartphone,
  RefreshCw,
  Edit3,
  CheckCircle2,
  Users,
  BadgeCheck,
  SunMedium,
  Contrast,
  Palette,
  Music2,
  Video,
  Film,
  ChevronDown,
  Play,
} from "lucide-react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import PlatformIcon from "@/components/shared/PlatformIcon";
import DevicePreview from "@/components/shared/DevicePreview";
import { cn } from "@/lib/utils";
import api, { getAccountId } from "@/lib/api";
import { showSuccess, showError } from "@/components/ui/Toast";

// ────────────────────────────────────────────────────────
// Types
// ────────────────────────────────────────────────────────
type Platform = "facebook" | "instagram" | "linkedin" | "twitter" | "youtube" | "tiktok" | "pinterest";
type Tone = "professional" | "casual" | "friendly" | "humorous" | "inspirational";
type MediaTab = "upload" | "ai-generate" | "photography";
type ImageStyle = "realistic" | "illustration" | "abstract" | "photography" | "3d-render";
type ImageSize = "square" | "portrait" | "landscape";
type PhotoTemplate = "product-shot" | "lifestyle" | "flat-lay" | "portrait" | "landscape-photo";
type DeviceType = "mobile" | "tablet" | "web";
type WizardStep = 1 | 2 | 3 | 4;

interface Account {
  id: string;
  platform: Platform;
  name: string;
  handle: string;
  verified: boolean;
  followers: number;
  avatar?: string;
}

// ────────────────────────────────────────────────────────
// Constants
// ────────────────────────────────────────────────────────
const TONES: { key: Tone; label: string }[] = [
  { key: "professional", label: "Professional" },
  { key: "casual", label: "Casual" },
  { key: "friendly", label: "Friendly" },
  { key: "humorous", label: "Humorous" },
  { key: "inspirational", label: "Inspirational" },
];

const IMAGE_STYLES: { key: ImageStyle; label: string }[] = [
  { key: "realistic", label: "Realistic" },
  { key: "illustration", label: "Illustration" },
  { key: "abstract", label: "Abstract" },
  { key: "photography", label: "Photography" },
  { key: "3d-render", label: "3D Render" },
];

const IMAGE_SIZES: { key: ImageSize; label: string }[] = [
  { key: "square", label: "Square" },
  { key: "portrait", label: "Portrait" },
  { key: "landscape", label: "Landscape" },
];

const PHOTO_TEMPLATES: { key: PhotoTemplate; label: string }[] = [
  { key: "product-shot", label: "Product Shot" },
  { key: "lifestyle", label: "Lifestyle" },
  { key: "flat-lay", label: "Flat Lay" },
  { key: "portrait", label: "Portrait" },
  { key: "landscape-photo", label: "Landscape" },
];



const STEPS = [
  { step: 1 as WizardStep, label: "Select Accounts" },
  { step: 2 as WizardStep, label: "Create Content" },
  { step: 3 as WizardStep, label: "Preview" },
  { step: 4 as WizardStep, label: "Post / Schedule" },
];



function formatFollowers(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return n.toString();
}

// Format seconds as m:ss for the audio scrubber.
function fmtTime(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

// ────────────────────────────────────────────────────────
// Step transition variants
// ────────────────────────────────────────────────────────
const stepVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 60 : -60,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
  },
  exit: (direction: number) => ({
    x: direction > 0 ? -60 : 60,
    opacity: 0,
  }),
};

// ────────────────────────────────────────────────────────
// Shimmer loading animation
// ────────────────────────────────────────────────────────
function ShimmerBlock({ className }: { className?: string }) {
  return (
    <div className={cn("relative overflow-hidden rounded-lg bg-white/5", className)}>
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/10 to-transparent" />
    </div>
  );
}

// ────────────────────────────────────────────────────────
// Main Page Component
// ────────────────────────────────────────────────────────
export default function CreatePostPage() {
  const navigate = useNavigate();
  // Wizard state
  const [currentStep, setCurrentStep] = useState<WizardStep>(1);
  const [direction, setDirection] = useState(1);

  // Step 1 - Content
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [aiPrompt, setAiPrompt] = useState("");
  const [selectedTone, setSelectedTone] = useState<Tone>("professional");
  const [isGeneratingContent, setIsGeneratingContent] = useState(false);
  const [hashtags, setHashtags] = useState<string[]>([]);
  const [hashtagInput, setHashtagInput] = useState("");

  // Media
  const [mediaTab, setMediaTab] = useState<MediaTab>("upload");
  const [uploadedImages, setUploadedImages] = useState<string[]>([]);
  const [aiImagePrompt, setAiImagePrompt] = useState("");
  const [imageStyle, setImageStyle] = useState<ImageStyle>("realistic");
  const [imageSize, setImageSize] = useState<ImageSize>("square");
  const [isGeneratingImage, setIsGeneratingImage] = useState(false);
  const [generatedImages, setGeneratedImages] = useState<string[]>([]);
  const [photoTemplate, setPhotoTemplate] = useState<PhotoTemplate>("product-shot");
  const [brightness, setBrightness] = useState(50);
  const [contrast, setContrast] = useState(50);
  const [saturation, setSaturation] = useState(50);

  // Step 2 - Accounts (loaded from API)
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountsLoading, setAccountsLoading] = useState(false);
  const [selectedAccounts, setSelectedAccounts] = useState<string[]>([]);
  const [businesses, setBusinesses] = useState<any[]>([]);

  useEffect(() => {
    const load = async () => {
      const activeAccountId = await getAccountId();
      if (!activeAccountId) return;
      setAccountsLoading(true);
      
      try {
        const res: any = await api.get(`/accounts/${activeAccountId}/social-accounts/`);
        const payload = res.data || res;
        const items: any[] = payload.items || payload || [];
        const mapped: Account[] = items.map((sa: any) => ({
          id: sa.id,
          platform: (
            sa.platform_type ||
            (sa.platform && typeof sa.platform === "object" ? sa.platform.slug || sa.platform.name : sa.platform) ||
            "instagram"
          ).toLowerCase() as Platform,
          name: sa.account_name || sa.name || sa.username || sa.platform_type,
          handle: sa.username ? `@${sa.username}` : sa.handle || "",
          verified: sa.is_verified || false,
          followers: sa.followers_count ?? sa.metadata?.followers ?? 0,
          avatar: sa.profile_image_url || sa.profile_picture_url || undefined,
        }));
        setAccounts(mapped);
      } catch (err) {
        console.error("Failed to load social accounts:", err);
      } finally {
        setAccountsLoading(false);
      }

      try {
        const res: any = await api.get(`/accounts/${activeAccountId}/businesses/`);
        const payload = res.data || res;
        const items = payload.items || payload.data?.items || [];
        setBusinesses(items);
      } catch (err) {
        console.error("Failed to load businesses:", err);
      }
    };
    load();
  }, []);

  // Step 3 - Preview
  const [previewDevice, setPreviewDevice] = useState<DeviceType>("mobile");

  // Step 4 - Schedule
  const [postMode, setPostMode] = useState<"now" | "schedule">("now");
  const [scheduleDate, setScheduleDate] = useState(() => {
    const d = new Date();
    d.setHours(d.getHours() + 1);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  });
  const [scheduleTime, setScheduleTime] = useState(() => {
    const d = new Date();
    d.setHours(d.getHours() + 1);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${hh}:${mm}`;
  });
  const [isPosting, setIsPosting] = useState(false);

  // ── Instagram & Facebook & YouTube & LinkedIn & Twitter formats ──
  const [igPostType, setIgPostType] = useState<"post" | "reel">("post");
  const [fbPostType, setFbPostType] = useState<"post" | "reel">("post");
  const [ytPostType, setYtPostType] = useState<"post" | "video">("post");
  const [liPostType, setLiPostType] = useState<"post" | "video">("post");
  const [twPostType, setTwPostType] = useState<"post" | "video">("post");
  const [igMusicTrack, setIgMusicTrack] = useState<string | null>(null);
  const [igMusicSearch, setIgMusicSearch] = useState("");
  const [igMusicOpen, setIgMusicOpen] = useState(false);
  const [videoPreviewUrl, setVideoPreviewUrl] = useState<string | null>(null);
  const [videoFileName, setVideoFileName] = useState<string | null>(null);

  // Real Audio Picker States
  const [selectedTrack, setSelectedTrack] = useState<any | null>(null);
  const [musicStartOffset, setMusicStartOffset] = useState<number>(0);
  const [musicEndOffset, setMusicEndOffset] = useState<number>(15);
  const [trackDuration, setTrackDuration] = useState<number>(30);
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [playingTrackId, setPlayingTrackId] = useState<string | null>(null);
  const [playhead, setPlayhead] = useState<number>(0); // current playback position (seconds) of the selected track
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const clipPreviewRef = useRef<boolean>(false); // true = loop inside [start,end]; false = play the full song

  // Audio cleanup on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  // Stop audio when picker is closed
  useEffect(() => {
    if (!igMusicOpen && audioRef.current) {
      audioRef.current.pause();
      setPlayingTrackId(null);
    }
  }, [igMusicOpen]);

  // Debounced search for iTunes
  const searchiTunes = useCallback(async (query: string) => {
    setSearchLoading(true);
    try {
      const term = query.trim() ? query.trim() : "tamil hits";
      const response = await fetch(`https://itunes.apple.com/search?term=${encodeURIComponent(term)}&media=music&limit=15`);
      const data = await response.json();
      setSearchResults(data.results || []);
    } catch (err) {
      console.error("Failed to search iTunes:", err);
    } finally {
      setSearchLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!igMusicOpen) return;
    const delayDebounceFn = setTimeout(() => {
      searchiTunes(igMusicSearch);
    }, 400);

    return () => clearTimeout(delayDebounceFn);
  }, [igMusicSearch, igMusicOpen, searchiTunes]);

  // Audio Playback handler.
  // `clipPreview` = false → play the FULL song (so the user can listen through it and
  // pick the position they want). `clipPreview` = true → loop inside the [start, end] window.
  const togglePlayTrack = useCallback((track: any, clipPreview = false) => {
    const trackId = String(track.trackId);
    if (!audioRef.current) {
      audioRef.current = new Audio();
    }

    if (playingTrackId === trackId && clipPreviewRef.current === clipPreview) {
      if (audioRef.current.paused) {
        audioRef.current.play().catch(e => console.error(e));
      } else {
        audioRef.current.pause();
        setPlayingTrackId(null);
      }
    } else {
      audioRef.current.pause();
      clipPreviewRef.current = clipPreview;
      audioRef.current.src = track.previewUrl;
      audioRef.current.load();

      audioRef.current.onloadedmetadata = () => {
        if (!audioRef.current) return;
        const dur = Number.isFinite(audioRef.current.duration) ? Math.floor(audioRef.current.duration) : 30;
        setTrackDuration(Math.max(1, dur));
      };

      const isSelected = selectedTrack?.trackId === track.trackId;
      // Clip preview starts at the trim start; full playback resumes from the current playhead.
      const start = clipPreview ? musicStartOffset : (isSelected ? playhead : 0);
      audioRef.current.currentTime = start;
      setPlayhead(start);

      audioRef.current.play()
        .then(() => {
          setPlayingTrackId(trackId);
        })
        .catch(e => {
          console.error("Audio playback failed:", e);
          setPlayingTrackId(null);
        });

      audioRef.current.onended = () => {
        setPlayingTrackId(null);
      };

      audioRef.current.ontimeupdate = () => {
        if (!audioRef.current) return;
        const current = audioRef.current.currentTime;
        setPlayhead(current);
        // Only loop when previewing the trimmed clip of the selected track.
        if (clipPreviewRef.current && selectedTrack && String(selectedTrack.trackId) === trackId) {
          if (current < musicStartOffset || current >= musicEndOffset) {
            audioRef.current.currentTime = musicStartOffset;
          }
        }
      };
    }
  }, [playingTrackId, selectedTrack, musicStartOffset, musicEndOffset, playhead]);

  // Seek to an absolute position (seconds) in the full song — "select the particular position".
  const seekTo = useCallback((seconds: number) => {
    const clamped = Math.min(Math.max(0, seconds), trackDuration);
    setPlayhead(clamped);
    if (audioRef.current && selectedTrack && playingTrackId === String(selectedTrack.trackId)) {
      audioRef.current.currentTime = clamped;
    }
  }, [trackDuration, selectedTrack, playingTrackId]);

  const selectTrack = useCallback((track: any) => {
    const isSelected = selectedTrack?.trackId === track.trackId;
    if (isSelected) {
      setSelectedTrack(null);
      setIgMusicTrack(null);
      setMusicStartOffset(0);
      setMusicEndOffset(15);
      setPlayhead(0);
      if (audioRef.current) {
        audioRef.current.pause();
        setPlayingTrackId(null);
      }
    } else {
      setSelectedTrack(track);
      setIgMusicTrack(`${track.trackName} – ${track.artistName}`);
      setMusicStartOffset(0);
      setMusicEndOffset(15);
      setTrackDuration(30);
      setPlayhead(0);
      if (audioRef.current && playingTrackId === String(track.trackId)) {
        audioRef.current.currentTime = 0;
      }
    }
  }, [selectedTrack, playingTrackId]);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const videoInputRef = useRef<HTMLInputElement>(null);
  const audioInputRef = useRef<HTMLInputElement>(null);

  // Upload an audio file from the user's device/folder and use it as the track.
  const handleAudioUpload = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result as string;
      const track = {
        trackId: `local-${file.name}-${file.size}`,
        trackName: file.name.replace(/\.[^.]+$/, ""),
        artistName: "Your upload",
        previewUrl: dataUrl,
        artworkUrl100: null,
        isLocal: true,
      };
      // Read real duration so the trim sliders span the whole file.
      const probe = new Audio();
      probe.src = dataUrl;
      probe.onloadedmetadata = () => {
        const dur = Number.isFinite(probe.duration) ? Math.floor(probe.duration) : 30;
        setTrackDuration(Math.max(1, dur));
        setMusicEndOffset(Math.min(15, Math.max(1, dur)));
      };
      setSelectedTrack(track);
      setIgMusicTrack(`${track.trackName} – ${track.artistName}`);
      setMusicStartOffset(0);
      setMusicEndOffset(15);
      setTrackDuration(30);
      setPlayhead(0);
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }, []);

  // ── Navigation ──
  const goToStep = useCallback(
    (step: WizardStep) => {
      setDirection(step > currentStep ? 1 : -1);
      setCurrentStep(step);
    },
    [currentStep]
  );

  const nextStep = useCallback(() => {
    if (currentStep < 4) goToStep((currentStep + 1) as WizardStep);
  }, [currentStep, goToStep]);

  const prevStep = useCallback(() => {
    if (currentStep > 1) goToStep((currentStep - 1) as WizardStep);
  }, [currentStep, goToStep]);

  // ── Handlers ──
  const handleGenerateContent = useCallback(async () => {
    if (!aiPrompt.trim()) return;

    const accountId = localStorage.getItem("account_id");
    if (!accountId) {
      showError("Account ID not found");
      return;
    }

    setIsGeneratingContent(true);
    try {
      const connectedPlatforms = Array.from(new Set(accounts.map((a) => a.platform)));
      const platforms = connectedPlatforms.length > 0 ? connectedPlatforms : ["instagram", "facebook"];
      const businessId = businesses.length > 0 ? businesses[0].id : undefined;

      const payload = {
        prompt: aiPrompt.trim(),
        platforms: platforms,
        tone: selectedTone,
        include_image: false,
        business_id: businessId,
      };

      const res: any = await api.post(`/accounts/${accountId}/ai/generate-content`, payload, { timeout: 90000 });
      const data = res.data || res;
      
      if (data && data.content) {
        setContent(data.content);
        if (data.hashtags && data.hashtags.length > 0) {
          // parse or extract hashtags (strip '#' character if present since page adds it dynamically)
          const cleanHashtags = data.hashtags.map((tag: string) => tag.replace(/^#/, ""));
          setHashtags(cleanHashtags);
        }
        showSuccess("Content generated successfully!");
      } else {
        throw new Error("No content returned from AI generator");
      }
    } catch (err: any) {
      console.error(err);
      const errMsg = err.response?.data?.detail || err.message || "Failed to generate content";
      showError(`AI Generation failed: ${errMsg}`);
    } finally {
      setIsGeneratingContent(false);
    }
  }, [aiPrompt, accounts, businesses, selectedTone]);

  const handleAiSuggestHashtags = useCallback(() => {
    const suggestions = ["marketing", "digitalstrategy", "socialmedia", "growthhacking", "branding", "contentcreation"];
    setHashtags((prev) => {
      const newTags = suggestions.filter((s) => !prev.includes(s));
      return [...prev, ...newTags.slice(0, 4)];
    });
  }, []);

  const addHashtag = useCallback(() => {
    const tag = hashtagInput.trim().replace(/^#/, "");
    if (tag && !hashtags.includes(tag)) {
      setHashtags((prev) => [...prev, tag]);
      setHashtagInput("");
    }
  }, [hashtagInput, hashtags]);

  const removeHashtag = useCallback((tag: string) => {
    setHashtags((prev) => prev.filter((t) => t !== tag));
  }, []);

  const handleFileUpload = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    Array.from(files).forEach((file) => {
      const reader = new FileReader();
      reader.onload = () => {
        setUploadedImages((prev) => [...prev, reader.result as string]);
      };
      reader.readAsDataURL(file);
    });
    e.target.value = "";
  }, []);

  const handleVideoUpload = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setVideoFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      setVideoPreviewUrl(reader.result as string);
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }, []);

  const handleGenerateImage = useCallback(async () => {
    if (!aiImagePrompt.trim()) return;

    const accountId = localStorage.getItem("account_id");
    if (!accountId) {
      showError("Account ID not found");
      return;
    }

    setIsGeneratingImage(true);
    try {
      const payload = {
        content: aiImagePrompt.trim(),
        style: imageStyle,
        size: imageSize,
      };

      const res: any = await api.post(`/accounts/${accountId}/ai/regenerate-image`, payload, { timeout: 90000 });
      const data = res.data || res;
      
      if (data && data.image_url) {
        setGeneratedImages([data.image_url]);
        showSuccess("Image generated successfully!");
      } else {
        throw new Error("No image URL returned from AI generator");
      }
    } catch (err: any) {
      console.error(err);
      const errMsg = err.response?.data?.detail || err.message || "Failed to generate image";
      showError(`AI Image Generation failed: ${errMsg}`);
    } finally {
      setIsGeneratingImage(false);
    }
  }, [aiImagePrompt, imageStyle, imageSize]);

  const toggleAccount = useCallback((id: string) => {
    setSelectedAccounts((prev) =>
      prev.includes(id) ? prev.filter((a) => a !== id) : [...prev, id]
    );
  }, []);

  const togglePlatformAll = useCallback(
    (platform: Platform) => {
      const platformAccounts = accounts.filter((a) => a.platform === platform);
      const allSelected = platformAccounts.every((a) => selectedAccounts.includes(a.id));
      if (allSelected) {
        setSelectedAccounts((prev) => prev.filter((id) => !platformAccounts.find((a) => a.id === id)));
      } else {
        setSelectedAccounts((prev) => {
          const newIds = platformAccounts.map((a) => a.id).filter((id) => !prev.includes(id));
          return [...prev, ...newIds];
        });
      }
    },
    [selectedAccounts]
  );

  const allImages = Array.from(
    new Set([
      ...uploadedImages,
      ...generatedImages.filter(
        (g) => uploadedImages.includes(g) || g.startsWith("generated-")
      ),
    ])
  );

  const handleConfirmPost = useCallback(async () => {
    const accountId = localStorage.getItem("account_id");
    if (!accountId) {
      showError("Account ID not found");
      return;
    }

    setIsPosting(true);
    try {
      // 1. Create post
      const payload: any = {
        title: title || undefined,
        content: content,
        hashtags: hashtags.length > 0 ? hashtags : undefined,
        target_account_ids: selectedAccounts,
        media_urls: allImages.length > 0 ? allImages : undefined,
        instagram_post_type: igPostType,
        instagram_music_track: igMusicTrack || undefined,
        instagram_music_url: selectedTrack?.previewUrl || undefined,
        instagram_music_start_offset: Math.round(musicStartOffset),
        instagram_music_end_offset: Math.round(musicEndOffset),
        instagram_video_url: videoPreviewUrl || undefined,
        facebook_post_type: fbPostType,
        facebook_music_track: igMusicTrack || undefined,
        facebook_music_url: selectedTrack?.previewUrl || undefined,
        facebook_music_start_offset: Math.round(musicStartOffset),
        facebook_music_end_offset: Math.round(musicEndOffset),
        facebook_video_url: videoPreviewUrl || undefined,
        youtube_post_type: ytPostType,
        linkedin_post_type: liPostType,
        twitter_post_type: twPostType,
      };

      const res: any = await api.post(`/accounts/${accountId}/posts/`, payload);
      const post = res.data || res;

      // 2. Publish or Schedule
      if (postMode === "now") {
        await api.post(`/accounts/${accountId}/posts/${post.id}/publish`);
        showSuccess("Post published successfully!");
      } else {
        const scheduledAt = new Date(`${scheduleDate}T${scheduleTime}:00`);
        if (isNaN(scheduledAt.getTime())) {
          throw new Error("Invalid schedule date or time");
        }
        await api.post(
          `/accounts/${accountId}/posts/${post.id}/schedule?scheduled_at=${encodeURIComponent(
            scheduledAt.toISOString()
          )}`
        );
        showSuccess("Post scheduled successfully!");
      }

      // Navigate to calendar page
      navigate("/calendar");
    } catch (err: any) {
      console.error(err);
      const errMsg = err.response?.data?.detail || err.message || "Failed to process request";
      showError(`Failed to confirm post: ${errMsg}`);
    } finally {
      setIsPosting(false);
    }
  }, [
    title,
    content,
    hashtags,
    selectedAccounts,
    allImages,
    postMode,
    scheduleDate,
    scheduleTime,
    navigate,
    igPostType,
    igMusicTrack,
    selectedTrack,
    musicStartOffset,
    musicEndOffset,
    videoPreviewUrl,
  ]);

  // Group accounts by platform
  const accountsByPlatform = accounts.reduce(
    (acc, account) => {
      if (!acc[account.platform]) acc[account.platform] = [];
      acc[account.platform].push(account);
      return acc;
    },
    {} as Record<Platform, Account[]>
  );

  const selectedPlatformCount = new Set(
    accounts.filter((a) => selectedAccounts.includes(a.id)).map((a) => a.platform)
  ).size;

  const hasSelectedInstagram = accounts
    .filter((a) => selectedAccounts.includes(a.id))
    .some((a) => a.platform === "instagram");
  const hasSelectedFacebook = accounts
    .filter((a) => selectedAccounts.includes(a.id))
    .some((a) => a.platform === "facebook");
  const hasSelectedYouTube = accounts
    .filter((a) => selectedAccounts.includes(a.id))
    .some((a) => a.platform === "youtube");
  const hasSelectedLinkedIn = accounts
    .filter((a) => selectedAccounts.includes(a.id))
    .some((a) => a.platform === "linkedin");
  const hasSelectedTwitter = accounts
    .filter((a) => selectedAccounts.includes(a.id))
    .some((a) => a.platform === "twitter");

  const isReelMode = (hasSelectedInstagram && igPostType === "reel") || 
                     (hasSelectedFacebook && fbPostType === "reel") ||
                     (hasSelectedYouTube && ytPostType === "video") ||
                     (hasSelectedLinkedIn && liPostType === "video") ||
                     (hasSelectedTwitter && twPostType === "video");

  // ────────────────────────────────────────────────────────
  // Render
  // ────────────────────────────────────────────────────────
  return (
    <DashboardLayout>
      {/* Shimmer keyframe (injected once) */}
      <style>{`@keyframes shimmer{100%{transform:translateX(100%)}}`}</style>

      <div className="max-w-7xl mx-auto space-y-6">
        {/* ── Page Header ── */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Create Post</h1>
            <p className="text-sm text-gray-400 mt-1">
              Craft, preview, and publish content across all your accounts
            </p>
          </div>
        </div>

        {/* ── Progress Bar ── */}
        <GlassCard padding="sm" className="!bg-white/[0.03]">
          <div className="flex items-center justify-between px-2">
            {STEPS.map((s, i) => {
              const isActive = currentStep === s.step;
              const isComplete = currentStep > s.step;
              return (
                <div key={s.step} className="flex items-center flex-1 last:flex-initial">
                  <button
                    onClick={() => {
                      if (isComplete) goToStep(s.step);
                    }}
                    disabled={!isComplete && !isActive}
                    className={cn(
                      "flex items-center gap-2.5 transition-all duration-300",
                      isComplete && "cursor-pointer",
                      !isComplete && !isActive && "cursor-default"
                    )}
                  >
                    <div
                      className={cn(
                        "w-9 h-9 rounded-xl flex items-center justify-center text-sm font-bold transition-all duration-300 flex-shrink-0",
                        isActive &&
                          "bg-gradient-to-r from-purple-600 to-blue-600 text-white shadow-lg shadow-purple-500/30",
                        isComplete &&
                          "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30",
                        !isActive &&
                          !isComplete &&
                          "bg-white/5 text-gray-500 border border-white/10"
                      )}
                    >
                      {isComplete ? <Check className="w-4 h-4" /> : s.step}
                    </div>
                    <span
                      className={cn(
                        "text-sm font-medium hidden sm:block transition-colors",
                        isActive && "text-white",
                        isComplete && "text-emerald-400",
                        !isActive && !isComplete && "text-gray-500"
                      )}
                    >
                      {s.label}
                    </span>
                  </button>
                  {i < STEPS.length - 1 && (
                    <div className="flex-1 mx-3 h-px">
                      <div
                        className={cn(
                          "h-full transition-colors duration-300",
                          currentStep > s.step
                            ? "bg-emerald-500/40"
                            : "bg-white/10"
                        )}
                      />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </GlassCard>

        {/* ── Step Content ── */}
        <AnimatePresence mode="wait" custom={direction}>
          {/* ═══════════════════════════════════════════════ */}
          {/* STEP 1: Create Content                         */}
          {/* ═══════════════════════════════════════════════ */}
          {currentStep === 2 && (
            <motion.div
              key="step2"
              custom={direction}
              variants={stepVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="grid grid-cols-1 lg:grid-cols-5 gap-6"
            >
              {/* Left Panel (60%) */}
              <div className="lg:col-span-3 space-y-5">
                {/* Title */}
                <GlassCard>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Post title - optional"
                    className="w-full bg-transparent text-white text-lg font-medium placeholder-gray-500 outline-none"
                  />
                </GlassCard>

                {/* AI Content Generator */}
                <div className="relative rounded-2xl p-[1px] bg-gradient-to-r from-purple-600/60 via-blue-500/40 to-purple-600/60">
                  <div className="rounded-2xl bg-slate-950/90 backdrop-blur-xl p-5 space-y-4">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                        <Sparkles className="w-4 h-4 text-white" />
                      </div>
                      <h3 className="text-sm font-semibold text-white">
                        Generate with AI
                      </h3>
                      <Badge variant="info" size="sm">Beta</Badge>
                    </div>

                    <textarea
                      value={aiPrompt}
                      onChange={(e) => setAiPrompt(e.target.value)}
                      placeholder="Describe what you want to post about..."
                      rows={3}
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 outline-none resize-none focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 transition-all"
                    />

                    {/* Tone pills */}
                    <div>
                      <p className="text-xs text-gray-400 mb-2">Tone</p>
                      <div className="flex flex-wrap gap-2">
                        {TONES.map((tone) => (
                          <button
                            key={tone.key}
                            onClick={() => setSelectedTone(tone.key)}
                            className={cn(
                              "px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 border",
                              selectedTone === tone.key
                                ? "bg-purple-500/20 border-purple-500/40 text-purple-300 shadow-sm shadow-purple-500/10"
                                : "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10 hover:text-gray-300"
                            )}
                          >
                            {tone.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <Button
                      onClick={handleGenerateContent}
                      loading={isGeneratingContent}
                      disabled={!aiPrompt.trim()}
                      icon={<Sparkles className="w-4 h-4" />}
                      className="w-full"
                    >
                      Generate Content
                    </Button>

                    {/* Shimmer loading state */}
                    {isGeneratingContent && (
                      <div className="space-y-2 pt-2">
                        <ShimmerBlock className="h-4 w-full" />
                        <ShimmerBlock className="h-4 w-4/5" />
                        <ShimmerBlock className="h-4 w-3/5" />
                      </div>
                    )}
                  </div>
                </div>

                {/* Content textarea */}
                <GlassCard>
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-sm font-medium text-gray-300">
                        Content
                      </label>
                      <span
                        className={cn(
                          "text-xs",
                          content.length > 2200 ? "text-red-400" : "text-gray-500"
                        )}
                      >
                        {content.length} / 2,200
                      </span>
                    </div>
                    <textarea
                      value={content}
                      onChange={(e) => setContent(e.target.value)}
                      placeholder="Write your post content here..."
                      className="w-full min-h-[250px] bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 outline-none resize-y focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 transition-all"
                    />
                  </div>
                </GlassCard>

                {/* Hashtag Manager */}
                <GlassCard>
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Hash className="w-4 h-4 text-purple-400" />
                      <h3 className="text-sm font-medium text-gray-300">
                        Hashtags
                      </h3>
                    </div>

                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={hashtagInput}
                        onChange={(e) => setHashtagInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && addHashtag()}
                        placeholder="Add a hashtag..."
                        className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-500 outline-none focus:border-purple-500/50 transition-all"
                      />
                      <Button size="md" variant="secondary" onClick={addHashtag}>
                        <Plus className="w-4 h-4" />
                      </Button>
                      <Button
                        size="md"
                        variant="ghost"
                        onClick={handleAiSuggestHashtags}
                        icon={<Sparkles className="w-3.5 h-3.5" />}
                      >
                        AI Suggest
                      </Button>
                    </div>

                    {hashtags.length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {hashtags.map((tag) => (
                          <motion.span
                            key={tag}
                            initial={{ scale: 0.8, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.8, opacity: 0 }}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-medium"
                          >
                            #{tag}
                            <button
                              onClick={() => removeHashtag(tag)}
                              className="ml-0.5 hover:text-blue-200 transition-colors"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </motion.span>
                        ))}
                      </div>
                    )}
                  </div>
                </GlassCard>
              </div>

              {/* Right Panel (40%) */}
              <div className="lg:col-span-2 space-y-5">
                {/* ── Instagram Post Type Selector ── */}
                {hasSelectedInstagram && (
                  <div className="rounded-2xl p-4 border border-white/10 bg-white/[0.03]">
                    <div className="flex items-center gap-2 mb-3">
                      <PlatformIcon platform="instagram" size="sm" showLabel />
                      <span className="text-xs text-gray-500">• Format</span>
                    </div>
                    <div className="flex gap-1.5 p-1 rounded-xl bg-black/20 border border-white/10">
                      <button
                        onClick={() => setIgPostType("post")}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all duration-200",
                          igPostType === "post"
                            ? "bg-gradient-to-r from-pink-500/25 to-orange-400/20 text-white border border-pink-500/30 shadow-sm shadow-pink-500/10"
                            : "text-gray-400 hover:text-gray-200"
                        )}
                        type="button"
                      >
                        <ImageIcon className="w-3.5 h-3.5" />
                        Post
                      </button>
                      <button
                        onClick={() => setIgPostType("reel")}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all duration-200",
                          igPostType === "reel"
                            ? "bg-gradient-to-r from-pink-500/25 to-orange-400/20 text-white border border-pink-500/30 shadow-sm shadow-pink-500/10"
                            : "text-gray-400 hover:text-gray-200"
                        )}
                        type="button"
                      >
                        <Film className="w-3.5 h-3.5" />
                        Reel
                      </button>
                    </div>
                    {igPostType === "reel" && (
                      <p className="text-[10px] text-pink-300/70 mt-2 text-center">Upload a vertical video · 9:16 recommended</p>
                    )}
                  </div>
                )}

                {hasSelectedFacebook && (
                  <div className="rounded-2xl p-4 border border-white/10 bg-white/[0.03]">
                    <div className="flex items-center gap-2 mb-3">
                      <PlatformIcon platform="facebook" size="sm" showLabel />
                      <span className="text-xs text-gray-500">• Format</span>
                    </div>
                    <div className="flex gap-1.5 p-1 rounded-xl bg-black/20 border border-white/10">
                      <button
                        onClick={() => setFbPostType("post")}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all duration-200",
                          fbPostType === "post"
                            ? "bg-gradient-to-r from-blue-500/25 to-sky-400/20 text-white border border-blue-500/30 shadow-sm shadow-blue-500/10"
                            : "text-gray-400 hover:text-gray-200"
                        )}
                        type="button"
                      >
                        <ImageIcon className="w-3.5 h-3.5" />
                        Post
                      </button>
                      <button
                        onClick={() => setFbPostType("reel")}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all duration-200",
                          fbPostType === "reel"
                            ? "bg-gradient-to-r from-blue-500/25 to-sky-400/20 text-white border border-blue-500/30 shadow-sm shadow-blue-500/10"
                            : "text-gray-400 hover:text-gray-200"
                        )}
                        type="button"
                      >
                        <Film className="w-3.5 h-3.5" />
                        Reel
                      </button>
                    </div>
                    {fbPostType === "reel" && (
                      <p className="text-[10px] text-blue-300/70 mt-2 text-center">Upload a vertical video · 9:16 recommended</p>
                    )}
                  </div>
                )}

                {hasSelectedYouTube && (
                  <div className="rounded-2xl p-4 border border-white/10 bg-white/[0.03]">
                    <div className="flex items-center gap-2 mb-3">
                      <PlatformIcon platform="youtube" size="sm" showLabel />
                      <span className="text-xs text-gray-500">• Format</span>
                    </div>
                    <div className="flex gap-1.5 p-1 rounded-xl bg-black/20 border border-white/10">
                      <button
                        onClick={() => setYtPostType("post")}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all duration-200",
                          ytPostType === "post"
                            ? "bg-gradient-to-r from-red-500/25 to-rose-400/20 text-white border border-red-500/30 shadow-sm shadow-red-500/10"
                            : "text-gray-400 hover:text-gray-200"
                        )}
                        type="button"
                      >
                        <ImageIcon className="w-3.5 h-3.5" />
                        Community Post
                      </button>
                      <button
                        onClick={() => setYtPostType("video")}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all duration-200",
                          ytPostType === "video"
                            ? "bg-gradient-to-r from-red-500/25 to-rose-400/20 text-white border border-red-500/30 shadow-sm shadow-red-500/10"
                            : "text-gray-400 hover:text-gray-200"
                        )}
                        type="button"
                      >
                        <Film className="w-3.5 h-3.5" />
                        Video / Shorts
                      </button>
                    </div>
                    {ytPostType === "video" && (
                      <p className="text-[10px] text-red-300/70 mt-2 text-center">Upload a vertical video · 9:16 recommended</p>
                    )}
                  </div>
                )}

                {hasSelectedLinkedIn && (
                  <div className="rounded-2xl p-4 border border-white/10 bg-white/[0.03]">
                    <div className="flex items-center gap-2 mb-3">
                      <PlatformIcon platform="linkedin" size="sm" showLabel />
                      <span className="text-xs text-gray-500">• Format</span>
                    </div>
                    <div className="flex gap-1.5 p-1 rounded-xl bg-black/20 border border-white/10">
                      <button
                        onClick={() => setLiPostType("post")}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all duration-200",
                          liPostType === "post"
                            ? "bg-gradient-to-r from-blue-600/25 to-sky-500/20 text-white border border-blue-600/30 shadow-sm shadow-blue-600/10"
                            : "text-gray-400 hover:text-gray-200"
                        )}
                        type="button"
                      >
                        <ImageIcon className="w-3.5 h-3.5" />
                        Post
                      </button>
                      <button
                        onClick={() => setLiPostType("video")}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all duration-200",
                          liPostType === "video"
                            ? "bg-gradient-to-r from-blue-600/25 to-sky-500/20 text-white border border-blue-600/30 shadow-sm shadow-blue-600/10"
                            : "text-gray-400 hover:text-gray-200"
                        )}
                        type="button"
                      >
                        <Film className="w-3.5 h-3.5" />
                        Video
                      </button>
                    </div>
                  </div>
                )}

                {hasSelectedTwitter && (
                  <div className="rounded-2xl p-4 border border-white/10 bg-white/[0.03]">
                    <div className="flex items-center gap-2 mb-3">
                      <PlatformIcon platform="twitter" size="sm" showLabel />
                      <span className="text-xs text-gray-500">• Format</span>
                    </div>
                    <div className="flex gap-1.5 p-1 rounded-xl bg-black/20 border border-white/10">
                      <button
                        onClick={() => setTwPostType("post")}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all duration-200",
                          twPostType === "post"
                            ? "bg-white/10 text-white border border-white/20 shadow-sm"
                            : "text-gray-400 hover:text-gray-200"
                        )}
                        type="button"
                      >
                        <ImageIcon className="w-3.5 h-3.5" />
                        Post
                      </button>
                      <button
                        onClick={() => setTwPostType("video")}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold transition-all duration-200",
                          twPostType === "video"
                            ? "bg-white/10 text-white border border-white/20 shadow-sm"
                            : "text-gray-400 hover:text-gray-200"
                        )}
                        type="button"
                      >
                        <Film className="w-3.5 h-3.5" />
                        Video
                      </button>
                    </div>
                  </div>
                )}

                {/* Image & Media Section */}
                <GlassCard className="!p-0 overflow-hidden">
                  {/* Tab bar */}
                  <div className="flex border-b border-white/10">
                    {(
                      [
                        { key: "upload" as MediaTab, label: "Upload", icon: <Upload className="w-3.5 h-3.5" /> },
                        { key: "ai-generate" as MediaTab, label: "AI Generate", icon: <Wand2 className="w-3.5 h-3.5" /> },
                        { key: "photography" as MediaTab, label: "Photography", icon: <Camera className="w-3.5 h-3.5" /> },
                      ] as const
                    ).map((tab) => (
                      <button
                        key={tab.key}
                        onClick={() => setMediaTab(tab.key)}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-1.5 px-3 py-3 text-xs font-medium transition-all duration-200 border-b-2",
                          mediaTab === tab.key
                            ? "border-purple-500 text-purple-300 bg-purple-500/5"
                            : "border-transparent text-gray-500 hover:text-gray-300 hover:bg-white/5"
                        )}
                      >
                        {tab.icon}
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  <div className="p-4">
                    {/* Upload Tab */}
                    {mediaTab === "upload" && (
                      <div className="space-y-4">
                        {isReelMode ? (
                          /* ── Reel: Video Upload ── */
                          <div className="space-y-3">
                            <button
                              onClick={() => videoInputRef.current?.click()}
                              className="w-full border-2 border-dashed border-white/10 rounded-xl p-8 flex flex-col items-center gap-3 hover:border-pink-500/30 hover:bg-pink-500/5 transition-all duration-200 group"
                              type="button"
                            >
                              <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center group-hover:bg-pink-500/10 transition-colors">
                                <Video className="w-5 h-5 text-gray-400 group-hover:text-pink-400 transition-colors" />
                              </div>
                              <div className="text-center">
                                <p className="text-sm text-gray-300">Upload Reel video</p>
                                <p className="text-xs text-gray-500 mt-1">MP4, MOV up to 100 MB · 9:16 recommended</p>
                              </div>
                            </button>
                            <input
                              ref={videoInputRef}
                              type="file"
                              accept="video/*"
                              onChange={handleVideoUpload}
                              className="hidden"
                            />
                            {videoPreviewUrl && (
                              <div className="relative rounded-xl overflow-hidden border border-white/10 bg-black/30">
                                <video
                                  src={videoPreviewUrl}
                                  className="w-full rounded-xl max-h-52 object-contain"
                                  controls
                                />
                                <div className="flex items-center justify-between px-2 py-1.5">
                                  <p className="text-[11px] text-gray-400 truncate flex-1 mr-2">{videoFileName}</p>
                                  <button
                                    onClick={() => { setVideoPreviewUrl(null); setVideoFileName(null); }}
                                    className="w-5 h-5 rounded-full bg-black/70 flex items-center justify-center text-white hover:bg-red-500 transition-colors flex-shrink-0"
                                    type="button"
                                  >
                                    <X className="w-2.5 h-2.5" />
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          /* ── Post: Image Upload ── */
                          <>
                            <button
                              onClick={() => fileInputRef.current?.click()}
                              className="w-full border-2 border-dashed border-white/10 rounded-xl p-8 flex flex-col items-center gap-3 hover:border-purple-500/30 hover:bg-purple-500/5 transition-all duration-200 group"
                              type="button"
                            >
                              <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center group-hover:bg-purple-500/10 transition-colors">
                                <Upload className="w-5 h-5 text-gray-400 group-hover:text-purple-400 transition-colors" />
                              </div>
                              <div className="text-center">
                                <p className="text-sm text-gray-300">
                                  Drag & drop or click to upload
                                </p>
                                <p className="text-xs text-gray-500 mt-1">
                                  PNG, JPG, GIF up to 10MB
                                </p>
                              </div>
                            </button>
                            <input
                              ref={fileInputRef}
                              type="file"
                              accept="image/*"
                              multiple
                              onChange={handleFileUpload}
                              className="hidden"
                            />

                            {/* Image preview grid */}
                            {uploadedImages.length > 0 && (
                              <div className="grid grid-cols-2 gap-2">
                                {uploadedImages.map((img, i) => (
                                  <div
                                    key={i}
                                    className="relative rounded-xl overflow-hidden border border-white/10 aspect-square group"
                                  >
                                    <img
                                      src={img}
                                      alt={`Upload ${i + 1}`}
                                      className="w-full h-full object-cover"
                                    />
                                    <button
                                      onClick={() =>
                                        setUploadedImages((prev) =>
                                          prev.filter((_, idx) => idx !== i)
                                        )
                                      }
                                      className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-black/70 flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500"
                                      type="button"
                                    >
                                      <X className="w-3 h-3" />
                                    </button>
                                  </div>
                                ))}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    )}

                    {/* AI Generate Tab */}
                    {mediaTab === "ai-generate" && (
                      <div className="space-y-4">
                        <textarea
                          value={aiImagePrompt}
                          onChange={(e) => setAiImagePrompt(e.target.value)}
                          placeholder="Describe the image you want to generate..."
                          rows={3}
                          className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder-gray-500 outline-none resize-none focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 transition-all"
                        />

                        {/* Style selector */}
                        <div>
                          <p className="text-xs text-gray-400 mb-2">Style</p>
                          <div className="flex flex-wrap gap-1.5">
                            {IMAGE_STYLES.map((s) => (
                              <button
                                key={s.key}
                                onClick={() => setImageStyle(s.key)}
                                className={cn(
                                  "px-2.5 py-1 rounded-lg text-[11px] font-medium transition-all border",
                                  imageStyle === s.key
                                    ? "bg-purple-500/20 border-purple-500/40 text-purple-300"
                                    : "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10"
                                )}
                              >
                                {s.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Size selector */}
                        <div>
                          <p className="text-xs text-gray-400 mb-2">Size</p>
                          <div className="flex gap-2">
                            {IMAGE_SIZES.map((s) => (
                              <button
                                key={s.key}
                                onClick={() => setImageSize(s.key)}
                                className={cn(
                                  "flex-1 py-1.5 rounded-lg text-[11px] font-medium transition-all border text-center",
                                  imageSize === s.key
                                    ? "bg-purple-500/20 border-purple-500/40 text-purple-300"
                                    : "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10"
                                )}
                              >
                                {s.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        <Button
                          onClick={handleGenerateImage}
                          loading={isGeneratingImage}
                          disabled={!aiImagePrompt.trim()}
                          icon={<Wand2 className="w-4 h-4" />}
                          className="w-full"
                        >
                          Generate Image
                        </Button>

                        {/* Generated images */}
                        {isGeneratingImage && (
                          <div className="grid grid-cols-2 gap-2">
                            {[1, 2, 3, 4].map((i) => (
                              <ShimmerBlock key={i} className="aspect-square rounded-xl" />
                            ))}
                          </div>
                        )}

                        {!isGeneratingImage && generatedImages.length > 0 && (
                          <div className="grid grid-cols-2 gap-2">
                            {generatedImages.map((img, i) => (
                              <div
                                key={i}
                                className="relative rounded-xl overflow-hidden border border-white/10 aspect-square bg-gradient-to-br from-purple-900/30 to-blue-900/30 flex flex-col items-center justify-center group"
                              >
                                {img.startsWith("data:") || img.startsWith("http") || img.startsWith("blob:") ? (
                                  <img
                                    src={img}
                                    alt={`Generated ${i + 1}`}
                                    className="w-full h-full object-cover"
                                  />
                                ) : (
                                  <>
                                    <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center mb-2">
                                      <ImageIcon className="w-5 h-5 text-gray-500" />
                                    </div>
                                    <span className="text-[10px] text-gray-500">
                                      Generated {i + 1}
                                    </span>
                                  </>
                                )}
                                <div className="absolute inset-0 bg-black/60 flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                  <button
                                    onClick={() =>
                                      setUploadedImages((prev) => [...prev, img])
                                    }
                                    className="px-2.5 py-1 rounded-lg bg-purple-500/80 text-white text-[10px] font-medium hover:bg-purple-500 transition-colors"
                                  >
                                    Use This
                                  </button>
                                  <button
                                    onClick={handleGenerateImage}
                                    className="px-2.5 py-1 rounded-lg bg-white/10 text-white text-[10px] font-medium hover:bg-white/20 transition-colors"
                                  >
                                    Redo
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Digital Photography Tab */}
                    {mediaTab === "photography" && (
                      <div className="space-y-4">
                        <p className="text-xs text-gray-400">
                          Create digital photography from your content
                        </p>

                        {/* Template selector */}
                        <div>
                          <p className="text-xs text-gray-400 mb-2">Template</p>
                          <div className="grid grid-cols-2 gap-1.5">
                            {PHOTO_TEMPLATES.map((t) => (
                              <button
                                key={t.key}
                                onClick={() => setPhotoTemplate(t.key)}
                                className={cn(
                                  "px-2.5 py-2 rounded-lg text-[11px] font-medium transition-all border text-center",
                                  photoTemplate === t.key
                                    ? "bg-purple-500/20 border-purple-500/40 text-purple-300"
                                    : "bg-white/5 border-white/10 text-gray-400 hover:bg-white/10"
                                )}
                              >
                                {t.label}
                              </button>
                            ))}
                          </div>
                        </div>

                        {/* Filter controls */}
                        <div className="space-y-3">
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <span className="flex items-center gap-1.5 text-xs text-gray-400">
                                <SunMedium className="w-3 h-3" /> Brightness
                              </span>
                              <span className="text-[10px] text-gray-500">{brightness}%</span>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={brightness}
                              onChange={(e) => setBrightness(Number(e.target.value))}
                              className="w-full h-1.5 rounded-full bg-white/10 appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-500 [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-purple-500/30"
                            />
                          </div>
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <span className="flex items-center gap-1.5 text-xs text-gray-400">
                                <Contrast className="w-3 h-3" /> Contrast
                              </span>
                              <span className="text-[10px] text-gray-500">{contrast}%</span>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={contrast}
                              onChange={(e) => setContrast(Number(e.target.value))}
                              className="w-full h-1.5 rounded-full bg-white/10 appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-500 [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-purple-500/30"
                            />
                          </div>
                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <span className="flex items-center gap-1.5 text-xs text-gray-400">
                                <Palette className="w-3 h-3" /> Saturation
                              </span>
                              <span className="text-[10px] text-gray-500">{saturation}%</span>
                            </div>
                            <input
                              type="range"
                              min={0}
                              max={100}
                              value={saturation}
                              onChange={(e) => setSaturation(Number(e.target.value))}
                              className="w-full h-1.5 rounded-full bg-white/10 appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-500 [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:shadow-purple-500/30"
                            />
                          </div>
                        </div>

                        {/* Color overlay */}
                        <div>
                          <p className="text-xs text-gray-400 mb-2">Color Overlay</p>
                          <div className="flex gap-2">
                            {[
                              "bg-transparent border border-white/20",
                              "bg-purple-500/40",
                              "bg-blue-500/40",
                              "bg-amber-500/40",
                              "bg-rose-500/40",
                              "bg-emerald-500/40",
                              "bg-slate-800/60",
                            ].map((color, i) => (
                              <button
                                key={i}
                                className={cn(
                                  "w-7 h-7 rounded-lg transition-all hover:scale-110",
                                  color
                                )}
                              />
                            ))}
                          </div>
                        </div>

                        {/* Preview area */}
                        <div className="aspect-video rounded-xl bg-gradient-to-br from-purple-900/20 to-blue-900/20 border border-white/5 flex items-center justify-center"
                          style={{
                            filter: `brightness(${brightness / 50}) contrast(${contrast / 50}) saturate(${saturation / 50})`,
                          }}
                        >
                          <div className="text-center">
                            <Camera className="w-8 h-8 text-gray-600 mx-auto mb-2" />
                            <p className="text-xs text-gray-500">
                              Photography Preview
                            </p>
                          </div>
                        </div>

                        <Button variant="primary" className="w-full">
                          Apply
                        </Button>
                      </div>
                    )}
                  </div>
                </GlassCard>

                {/* ── Music Picker (Instagram) ── */}
                {(hasSelectedInstagram || hasSelectedFacebook) && (
                  <GlassCard>
                    <button
                      className="w-full flex items-center justify-between"
                      onClick={() => setIgMusicOpen((v) => !v)}
                      type="button"
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "linear-gradient(135deg,#7c3aed40,#ec489940)" }}>
                          <Music2 className="w-3.5 h-3.5 text-purple-300" />
                        </div>
                        <span className="text-sm font-semibold text-gray-300">Add Music</span>
                        {igMusicTrack && (
                          <span className="px-2 py-0.5 rounded-full bg-purple-500/15 border border-purple-500/25 text-purple-300 text-[11px] font-medium truncate max-w-[130px]">
                            ♫ {igMusicTrack.split(" – ")[0]}
                          </span>
                        )}
                      </div>
                      <ChevronDown className={cn("w-4 h-4 text-gray-500 transition-transform duration-200", igMusicOpen && "rotate-180")} />
                    </button>

                    <AnimatePresence>
                      {igMusicOpen && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden"
                        >
                          <div className="pt-4 space-y-3">
                            {/* Selected Track & Trim Controls */}
                            {selectedTrack && (
                              <div className="rounded-xl bg-purple-500/10 border border-purple-500/20 p-3.5 space-y-3">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-3">
                                    <div className="relative w-10 h-10 rounded-lg overflow-hidden bg-white/5 flex-shrink-0 group">
                                      {selectedTrack.artworkUrl100 ? (
                                        <img src={selectedTrack.artworkUrl100} alt="Cover" className="w-full h-full object-cover" />
                                      ) : (
                                        <Music2 className="w-5 h-5 text-purple-300 m-auto mt-2.5" />
                                      )}
                                      <button
                                        onClick={() => togglePlayTrack(selectedTrack)}
                                        className="absolute inset-0 bg-black/50 flex items-center justify-center text-white opacity-0 group-hover:opacity-100 transition-opacity"
                                        type="button"
                                      >
                                        {playingTrackId === String(selectedTrack.trackId) ? (
                                          <span className="w-2.5 h-2.5 bg-white rounded-sm animate-pulse" />
                                        ) : (
                                          <Play className="w-3.5 h-3.5 fill-white text-white" />
                                        )}
                                      </button>
                                    </div>
                                    <div className="min-w-0 text-left">
                                      <p className="text-xs font-bold text-purple-200 truncate">{selectedTrack.trackName}</p>
                                      <p className="text-[10px] text-purple-400 truncate">{selectedTrack.artistName}</p>
                                    </div>
                                  </div>
                                  <button onClick={() => selectTrack(selectedTrack)} className="text-purple-400 hover:text-purple-200 transition-colors p-1" type="button">
                                    <X className="w-4 h-4" />
                                  </button>
                                </div>

                                {/* Full-song player — play the whole track & scrub to any position */}
                                <div className="space-y-2 border-t border-purple-500/10 pt-3">
                                  <div className="flex items-center gap-2">
                                    <button
                                      onClick={() => togglePlayTrack(selectedTrack, false)}
                                      type="button"
                                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-[11px] font-semibold text-white transition-all flex-shrink-0"
                                    >
                                      {playingTrackId === String(selectedTrack.trackId) && !clipPreviewRef.current ? (
                                        <>
                                          <span className="w-2 h-2 bg-white rounded-sm" /> Pause
                                        </>
                                      ) : (
                                        <>
                                          <Play className="w-3 h-3 fill-white text-white" /> Play full song
                                        </>
                                      )}
                                    </button>
                                    <span className="text-[10px] text-gray-400 tabular-nums flex-shrink-0">
                                      {fmtTime(playhead)} / {fmtTime(trackDuration)}
                                    </span>
                                  </div>

                                  {/* Scrubber — drag to select the particular position */}
                                  <input
                                    type="range"
                                    min={0}
                                    max={trackDuration}
                                    step={0.1}
                                    value={playhead}
                                    onChange={(e) => seekTo(Number(e.target.value))}
                                    className="w-full h-1.5 rounded-full bg-white/10 appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3.5 [&::-webkit-slider-thumb]:h-3.5 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white [&::-webkit-slider-thumb]:shadow-lg"
                                  />

                                  {/* Set the trim window from the current playhead position */}
                                  <div className="flex items-center gap-2">
                                    <button
                                      onClick={() => {
                                        const val = Math.min(playhead, musicEndOffset - 1);
                                        setMusicStartOffset(Math.max(0, val));
                                      }}
                                      type="button"
                                      className="flex-1 py-1.5 rounded-lg bg-purple-500/15 hover:bg-purple-500/25 border border-purple-500/25 text-[10px] font-semibold text-purple-200 transition-all"
                                    >
                                      ⇤ Set start here
                                    </button>
                                    <button
                                      onClick={() => {
                                        const val = Math.max(playhead, musicStartOffset + 1);
                                        setMusicEndOffset(Math.min(trackDuration, val));
                                      }}
                                      type="button"
                                      className="flex-1 py-1.5 rounded-lg bg-pink-500/15 hover:bg-pink-500/25 border border-pink-500/25 text-[10px] font-semibold text-pink-200 transition-all"
                                    >
                                      Set end here ⇥
                                    </button>
                                    <button
                                      onClick={() => togglePlayTrack(selectedTrack, true)}
                                      type="button"
                                      className="flex-1 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-[10px] font-semibold text-white transition-all"
                                    >
                                      ▶ Preview clip
                                    </button>
                                  </div>
                                </div>

                                {/* Instagram Clip Trim — choose start & end */}
                                <div className="space-y-2.5 px-1 py-1 border-t border-purple-500/10 pt-3">
                                  <div className="flex items-center justify-between text-[10px] text-purple-300/80">
                                    <span className="font-semibold flex items-center gap-1">
                                      <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping" />
                                      Start {musicStartOffset.toFixed(1)}s
                                    </span>
                                    <span className="px-1.5 py-0.5 rounded-full bg-purple-500/20 text-purple-200 font-semibold">
                                      Clip {(musicEndOffset - musicStartOffset).toFixed(1)}s
                                    </span>
                                    <span>End {musicEndOffset.toFixed(1)}s</span>
                                  </div>

                                  {/* Visual selection window */}
                                  <div className="relative h-1.5 rounded-full bg-white/10 overflow-hidden">
                                    <div
                                      className="absolute h-full rounded-full bg-gradient-to-r from-purple-500 to-pink-500"
                                      style={{
                                        left: `${(musicStartOffset / trackDuration) * 100}%`,
                                        right: `${Math.max(0, 100 - (musicEndOffset / trackDuration) * 100)}%`,
                                      }}
                                    />
                                  </div>

                                  {/* Start handle */}
                                  <div>
                                    <div className="flex justify-between text-[9px] text-gray-400 font-semibold mb-0.5">
                                      <span>Start point</span>
                                    </div>
                                    <input
                                      type="range"
                                      min={0}
                                      max={trackDuration}
                                      step={0.5}
                                      value={musicStartOffset}
                                      onChange={(e) => {
                                        let val = Number(e.target.value);
                                        if (val > musicEndOffset - 1) val = Math.max(0, musicEndOffset - 1);
                                        setMusicStartOffset(val);
                                        if (audioRef.current && playingTrackId === String(selectedTrack.trackId)) {
                                          audioRef.current.currentTime = val;
                                        }
                                      }}
                                      className="w-full h-1 rounded-full bg-white/10 appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-500 [&::-webkit-slider-thumb]:shadow-lg"
                                    />
                                  </div>

                                  {/* End handle */}
                                  <div>
                                    <div className="flex justify-between text-[9px] text-gray-400 font-semibold mb-0.5">
                                      <span>End point</span>
                                    </div>
                                    <input
                                      type="range"
                                      min={0}
                                      max={trackDuration}
                                      step={0.5}
                                      value={musicEndOffset}
                                      onChange={(e) => {
                                        let val = Number(e.target.value);
                                        if (val < musicStartOffset + 1) val = Math.min(trackDuration, musicStartOffset + 1);
                                        setMusicEndOffset(val);
                                        if (audioRef.current && playingTrackId === String(selectedTrack.trackId)) {
                                          audioRef.current.currentTime = musicStartOffset;
                                        }
                                      }}
                                      className="w-full h-1 rounded-full bg-white/10 appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-pink-500 [&::-webkit-slider-thumb]:shadow-lg"
                                    />
                                  </div>

                                  <div className="flex justify-between text-[8px] text-gray-500 font-semibold pt-0.5">
                                    <span>0s</span>
                                    <span>{(trackDuration / 2).toFixed(0)}s</span>
                                    <span>{trackDuration.toFixed(0)}s</span>
                                  </div>
                                </div>
                              </div>
                            )}

                            {/* Search input */}
                            <div className="relative">
                              <input
                                type="text"
                                value={igMusicSearch}
                                onChange={(e) => setIgMusicSearch(e.target.value)}
                                placeholder="Search real songs on Instagram..."
                                className="w-full bg-white/5 border border-white/10 rounded-xl pl-4 pr-10 py-2.5 text-sm text-white placeholder-gray-500 outline-none focus:border-purple-500/50 focus:ring-2 focus:ring-purple-500/20 transition-all"
                              />
                              {searchLoading && (
                                <RefreshCw className="absolute right-3.5 top-3.5 w-3.5 h-3.5 text-purple-400 animate-spin" />
                              )}
                            </div>

                            {/* Upload your own audio from device / folder */}
                            <button
                              onClick={() => audioInputRef.current?.click()}
                              type="button"
                              className="w-full flex items-center justify-center gap-2 py-2 rounded-xl border border-dashed border-white/15 text-xs font-medium text-gray-300 hover:border-purple-500/40 hover:bg-purple-500/5 transition-all"
                            >
                              <Upload className="w-3.5 h-3.5" />
                              Upload audio from device
                            </button>
                            <input
                              ref={audioInputRef}
                              type="file"
                              accept="audio/*"
                              onChange={handleAudioUpload}
                              className="hidden"
                            />

                            {/* Search results list */}
                            <div className="space-y-1 max-h-56 overflow-y-auto pr-1">
                              {searchResults.map((track) => {
                                const trackId = String(track.trackId);
                                const isSelected = selectedTrack?.trackId === track.trackId;
                                const isPlaying = playingTrackId === trackId;
                                return (
                                  <div
                                    key={trackId}
                                    className={cn(
                                      "w-full flex items-center justify-between p-2 rounded-xl transition-all duration-150 border text-left",
                                      isSelected
                                        ? "bg-purple-500/15 border-purple-500/30"
                                        : "bg-white/[0.02] border-white/5 hover:bg-white/5 hover:border-white/10"
                                    )}
                                  >
                                    <div className="flex items-center gap-3 min-w-0 flex-1">
                                      {/* Cover art with Play/Pause overlay */}
                                      <div className="relative w-8 h-8 rounded-lg overflow-hidden bg-white/5 flex-shrink-0 group">
                                        {track.artworkUrl100 ? (
                                          <img src={track.artworkUrl100} alt="Art" className="w-full h-full object-cover" />
                                        ) : (
                                          <Music2 className="w-4 h-4 text-gray-400 m-auto mt-2" />
                                        )}
                                        <button
                                          onClick={() => togglePlayTrack(track)}
                                          className={cn(
                                            "absolute inset-0 bg-black/60 flex items-center justify-center text-white transition-opacity",
                                            isPlaying ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                                          )}
                                          type="button"
                                        >
                                          {isPlaying ? (
                                            <span className="w-2 h-2 bg-white rounded-sm animate-pulse" />
                                          ) : (
                                            <Play className="w-3 h-3 fill-white text-white" />
                                          )}
                                        </button>
                                      </div>

                                      <div className="min-w-0 flex-1">
                                        <p className="text-xs font-semibold truncate text-white">{track.trackName}</p>
                                        <p className="text-[10px] text-gray-500 truncate">{track.artistName}</p>
                                      </div>
                                    </div>

                                    {/* Action button */}
                                    <button
                                      onClick={() => selectTrack(track)}
                                      className={cn(
                                        "px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all flex items-center gap-1",
                                        isSelected
                                          ? "bg-purple-500 text-white shadow-sm"
                                          : "bg-white/5 hover:bg-purple-500/20 text-gray-300 hover:text-white"
                                      )}
                                      type="button"
                                    >
                                      {isSelected ? (
                                        <>
                                          <Check className="w-3 h-3" />
                                          Selected
                                        </>
                                      ) : (
                                        "Select"
                                      )}
                                    </button>
                                  </div>
                                );
                              })}

                              {!searchLoading && searchResults.length === 0 && (
                                <p className="text-[11px] text-gray-500 text-center py-4">
                                  No songs found. Type above to search.
                                </p>
                              )}
                            </div>
                            <p className="text-[10px] text-gray-600 text-center pt-1">
                              Streamed songs preview 30s &middot; Upload a file to play the full song &middot; Scrub to pick your position, then Set start/end
                            </p>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </GlassCard>
                )}

                {/* Next button */}
                <div className="flex gap-3 mt-4">
                  <Button variant="secondary" onClick={prevStep} icon={<ArrowLeft className="w-4 h-4" />} size="lg">
                    Back
                  </Button>
                  <Button
                    onClick={nextStep}
                    size="lg"
                    fullWidth
                    icon={<ArrowRight className="w-4 h-4" />}
                    iconPosition="right"
                    disabled={!content.trim()}
                  >
                    Next: Preview
                  </Button>
                </div>
              </div>
            </motion.div>
          )}

          {/* ═══════════════════════════════════════════════ */}
          {/* STEP 2: Select Target Accounts                 */}
          {/* ═══════════════════════════════════════════════ */}
          {currentStep === 1 && (
            <motion.div
              key="step1"
              custom={direction}
              variants={stepVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="space-y-5"
            >
              <div className="text-center mb-2">
                <h2 className="text-xl font-bold text-white">
                  Where should this post go?
                </h2>
                <p className="text-sm text-gray-400 mt-1">
                  Select the accounts you want to publish to
                </p>
              </div>

              {accountsLoading ? (
                <div className="flex items-center justify-center py-12 gap-3">
                  <RefreshCw className="w-5 h-5 text-purple-400 animate-spin" />
                  <span className="text-slate-400 text-sm">Loading your connected accounts…</span>
                </div>
              ) : accounts.length === 0 ? (
                <div className="text-center py-12">
                  <Users className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                  <p className="text-slate-400 text-sm mb-1">No social accounts connected yet</p>
                  <p className="text-xs text-slate-500">Go to <strong className="text-purple-400">Social Accounts</strong> to connect your profiles first.</p>
                </div>
              ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                {(Object.entries(accountsByPlatform) as [Platform, Account[]][]).map(
                  ([platform, accounts]) => {
                    const allSelected = accounts.every((a) =>
                      selectedAccounts.includes(a.id)
                    );
                    return (
                      <GlassCard key={platform}>
                        {/* Platform header */}
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2.5">
                            <PlatformIcon platform={platform} size="md" showLabel />
                          </div>
                          <label className="flex items-center gap-2 cursor-pointer group">
                            <span className="text-xs text-gray-500 group-hover:text-gray-300 transition-colors">
                              Select All
                            </span>
                            <button
                              onClick={() => togglePlatformAll(platform)}
                              className={cn(
                                "w-5 h-5 rounded-md flex items-center justify-center transition-all duration-200 border",
                                allSelected
                                  ? "bg-purple-500 border-purple-500 text-white"
                                  : "bg-white/5 border-white/20 hover:border-purple-500/50"
                              )}
                            >
                              {allSelected && <Check className="w-3 h-3" />}
                            </button>
                          </label>
                        </div>

                        {/* Account list */}
                        <div className="space-y-2">
                          {accounts.map((account) => {
                            const isSelected = selectedAccounts.includes(account.id);
                            return (
                              <button
                                key={account.id}
                                onClick={() => toggleAccount(account.id)}
                                className={cn(
                                  "w-full flex items-center gap-3 p-3 rounded-xl transition-all duration-200 border text-left",
                                  isSelected
                                    ? "bg-purple-500/10 border-purple-500/30 shadow-sm shadow-purple-500/5"
                                    : "bg-white/[0.02] border-white/5 hover:bg-white/5 hover:border-white/10"
                                )}
                              >
                                {/* Avatar */}
                                <div className="w-9 h-9 rounded-full bg-gradient-to-br from-purple-500/30 to-blue-500/30 flex items-center justify-center flex-shrink-0 text-xs font-bold text-white/60">
                                  {account.name.charAt(0)}
                                </div>

                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-sm font-medium text-white truncate">
                                      {account.name}
                                    </span>
                                    {account.verified && (
                                      <BadgeCheck className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                                    )}
                                  </div>
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs text-gray-500 truncate">
                                      {account.handle}
                                    </span>
                                    <span className="text-[10px] text-gray-600">
                                      {formatFollowers(account.followers)} followers
                                    </span>
                                  </div>
                                </div>

                                {/* Checkbox */}
                                <div
                                  className={cn(
                                    "w-5 h-5 rounded-md flex items-center justify-center transition-all duration-200 border flex-shrink-0",
                                    isSelected
                                      ? "bg-purple-500 border-purple-500 text-white"
                                      : "bg-white/5 border-white/20"
                                  )}
                                >
                                  {isSelected && <Check className="w-3 h-3" />}
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </GlassCard>
                    );
                  }
                )}
              </div>
              )}

              {/* Summary bar */}
              <GlassCard
                padding="sm"
                glow={selectedAccounts.length > 0}
                className="!bg-white/[0.03]"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-purple-400" />
                    <span className="text-sm text-gray-300">
                      {selectedAccounts.length > 0 ? (
                        <>
                          <span className="font-semibold text-white">
                            {selectedAccounts.length}
                          </span>{" "}
                          account{selectedAccounts.length !== 1 && "s"} selected
                          across{" "}
                          <span className="font-semibold text-white">
                            {selectedPlatformCount}
                          </span>{" "}
                          platform{selectedPlatformCount !== 1 && "s"}
                        </>
                      ) : (
                        "No accounts selected"
                      )}
                    </span>
                  </div>
                </div>
              </GlassCard>

              {/* Navigation */}
              <div className="flex gap-3">
                <Button
                  onClick={nextStep}
                  size="lg"
                  fullWidth
                  icon={<ArrowRight className="w-4 h-4" />}
                  iconPosition="right"
                  disabled={selectedAccounts.length === 0}
                >
                  Next: Create Content
                </Button>
              </div>
            </motion.div>
          )}

          {/* ═══════════════════════════════════════════════ */}
          {/* STEP 3: Multi-Device Preview                   */}
          {/* ═══════════════════════════════════════════════ */}
          {currentStep === 3 && (
            <motion.div
              key="step3"
              custom={direction}
              variants={stepVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="space-y-5"
            >
              {/* Device tab bar */}
              <GlassCard padding="sm" className="!bg-white/[0.03]">
                <div className="flex items-center gap-1 p-1 rounded-xl bg-white/5 border border-white/10">
                  {(
                    [
                      { key: "mobile" as DeviceType, label: "Mobile", icon: <Smartphone className="w-4 h-4" /> },
                      { key: "tablet" as DeviceType, label: "Tablet", icon: <Tablet className="w-4 h-4" /> },
                      { key: "web" as DeviceType, label: "Web", icon: <Monitor className="w-4 h-4" /> },
                    ] as const
                  ).map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setPreviewDevice(tab.key)}
                      className={cn(
                        "flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 flex-1",
                        previewDevice === tab.key
                          ? "bg-gradient-to-r from-purple-600/20 to-blue-600/20 text-white border border-purple-500/20 shadow-lg shadow-purple-500/5"
                          : "text-gray-400 hover:text-white"
                      )}
                    >
                      {tab.icon}
                      {tab.label}
                    </button>
                  ))}
                </div>
              </GlassCard>

              {/* Device frame */}
              <div className="flex justify-center py-4">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={previewDevice}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: 0.25 }}
                    className={cn(
                      "w-full",
                      previewDevice === "mobile" && "max-w-[280px]",
                      previewDevice === "tablet" && "max-w-[620px]",
                      previewDevice === "web" && "max-w-[960px]"
                    )}
                  >
                    <DevicePreview
                      content={content}
                      images={allImages}
                      videoUrl={videoPreviewUrl || null}
                      hashtags={hashtags}
                      device={previewDevice}
                      platformName={
                        accounts.find((a) => selectedAccounts.includes(a.id))
                          ?.platform ?? "Social Feed"
                      }
                      igPostType={igPostType}
                      igMusicTrack={igMusicTrack}
                    />
                  </motion.div>
                </AnimatePresence>
              </div>

              {/* Satisfied section */}
              <GlassCard>
                <div className="text-center space-y-4">
                  <h3 className="text-lg font-semibold text-white">
                    Satisfied with the preview?
                  </h3>
                  <p className="text-sm text-gray-400">
                    You can go back to edit or regenerate content, or proceed to publish.
                  </p>
                  <div className="flex flex-col sm:flex-row gap-3 justify-center">
                    <Button
                      variant="ghost"
                      onClick={() => goToStep(1)}
                      icon={<RefreshCw className="w-4 h-4" />}
                    >
                      Regenerate Content
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => goToStep(1)}
                      icon={<Edit3 className="w-4 h-4" />}
                    >
                      Edit Content
                    </Button>
                    <Button
                      onClick={nextStep}
                      icon={<CheckCircle2 className="w-4 h-4" />}
                      iconPosition="right"
                    >
                      Looks Good!
                    </Button>
                  </div>
                </div>
              </GlassCard>
            </motion.div>
          )}

          {/* ═══════════════════════════════════════════════ */}
          {/* STEP 4: Post / Schedule                        */}
          {/* ═══════════════════════════════════════════════ */}
          {currentStep === 4 && (
            <motion.div
              key="step4"
              custom={direction}
              variants={stepVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.3, ease: "easeInOut" }}
              className="space-y-5"
            >
              {/* Summary card */}
              <GlassCard>
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
                  Summary
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {/* Content preview */}
                  <div className="md:col-span-2 space-y-3">
                    {title && (
                      <p className="text-base font-semibold text-white">{title}</p>
                    )}
                    <p className="text-sm text-gray-300 whitespace-pre-wrap line-clamp-4">
                      {content}
                    </p>
                    {hashtags.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {hashtags.map((tag) => (
                          <span
                            key={tag}
                            className="text-xs text-blue-400 font-medium"
                          >
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                    {allImages.length > 0 && (
                      <div className="flex gap-2 mt-2">
                        {allImages.slice(0, 4).map((img, i) => (
                          <div
                            key={i}
                            className="w-14 h-14 rounded-lg bg-gradient-to-br from-purple-900/30 to-blue-900/30 border border-white/10 flex items-center justify-center overflow-hidden"
                          >
                            {img.startsWith("data:") || img.startsWith("http") || img.startsWith("blob:") ? (
                              <img src={img} alt="" className="w-full h-full object-cover" />
                            ) : (
                              <ImageIcon className="w-4 h-4 text-gray-500" />
                            )}
                          </div>
                        ))}
                        {allImages.length > 4 && (
                          <div className="w-14 h-14 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center text-xs text-gray-400 font-medium">
                            +{allImages.length - 4}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Instagram Reel / Music badges */}
                  {(igPostType === "reel" || igMusicTrack) && (
                    <div className="flex flex-wrap gap-2 pt-1 pb-3">
                      {igPostType === "reel" && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border" style={{ background: "linear-gradient(135deg,#f0943320,#dc274320)", borderColor: "#f09433aa", color: "#f09433" }}>
                          <Film className="w-3 h-3" />
                          Reel
                          {videoFileName && <span className="opacity-60 max-w-[80px] truncate">· {videoFileName}</span>}
                        </span>
                      )}
                      {igMusicTrack && (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-purple-500/15 border border-purple-500/30 text-purple-300 text-[11px] font-semibold">
                          <Music2 className="w-3 h-3" />
                          {igMusicTrack.split(" – ")[0]}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Target accounts */}
                  <div>
                    <p className="text-xs text-gray-400 mb-2">Publishing to</p>
                    <div className="space-y-1.5">
                      {accounts.filter((a) =>
                        selectedAccounts.includes(a.id)
                      ).map((account) => (
                        <div
                          key={account.id}
                          className="flex items-center gap-2 text-xs"
                        >
                          <PlatformIcon platform={account.platform} size="sm" />
                          <span className="text-gray-300 truncate">
                            {account.name}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </GlassCard>

              {/* Post options */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Post Now */}
                <button
                  onClick={() => setPostMode("now")}
                  className={cn(
                    "text-left rounded-2xl p-6 transition-all duration-300 border-2 group",
                    postMode === "now"
                      ? "bg-gradient-to-br from-purple-600/10 to-blue-600/10 border-purple-500/40 shadow-lg shadow-purple-500/10"
                      : "bg-white/[0.02] border-white/10 hover:border-white/20 hover:bg-white/[0.04]"
                  )}
                >
                  <div className="flex items-start gap-4">
                    <div
                      className={cn(
                        "w-14 h-14 rounded-2xl flex items-center justify-center transition-all flex-shrink-0",
                        postMode === "now"
                          ? "bg-gradient-to-br from-purple-500 to-blue-500 shadow-lg shadow-purple-500/30"
                          : "bg-white/5 group-hover:bg-white/10"
                      )}
                    >
                      <Rocket
                        className={cn(
                          "w-6 h-6 transition-colors",
                          postMode === "now" ? "text-white" : "text-gray-400"
                        )}
                      />
                    </div>
                    <div>
                      <h3
                        className={cn(
                          "text-lg font-semibold transition-colors",
                          postMode === "now" ? "text-white" : "text-gray-300"
                        )}
                      >
                        Post Now
                      </h3>
                      <p className="text-sm text-gray-400 mt-1">
                        Publish to {selectedAccounts.length} account
                        {selectedAccounts.length !== 1 && "s"} immediately
                      </p>
                    </div>
                  </div>
                  {postMode === "now" && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      className="mt-4 pt-4 border-t border-purple-500/20"
                    >
                      <p className="text-xs text-purple-300">
                        Your post will be published across all selected accounts within seconds.
                      </p>
                    </motion.div>
                  )}
                </button>

                {/* Schedule */}
                <button
                  onClick={() => setPostMode("schedule")}
                  className={cn(
                    "text-left rounded-2xl p-6 transition-all duration-300 border-2 group",
                    postMode === "schedule"
                      ? "bg-gradient-to-br from-purple-600/10 to-blue-600/10 border-purple-500/40 shadow-lg shadow-purple-500/10"
                      : "bg-white/[0.02] border-white/10 hover:border-white/20 hover:bg-white/[0.04]"
                  )}
                >
                  <div className="flex items-start gap-4">
                    <div
                      className={cn(
                        "w-14 h-14 rounded-2xl flex items-center justify-center transition-all flex-shrink-0",
                        postMode === "schedule"
                          ? "bg-gradient-to-br from-purple-500 to-blue-500 shadow-lg shadow-purple-500/30"
                          : "bg-white/5 group-hover:bg-white/10"
                      )}
                    >
                      <CalendarDays
                        className={cn(
                          "w-6 h-6 transition-colors",
                          postMode === "schedule" ? "text-white" : "text-gray-400"
                        )}
                      />
                    </div>
                    <div>
                      <h3
                        className={cn(
                          "text-lg font-semibold transition-colors",
                          postMode === "schedule" ? "text-white" : "text-gray-300"
                        )}
                      >
                        Schedule
                      </h3>
                      <p className="text-sm text-gray-400 mt-1">
                        Schedule for later
                      </p>
                    </div>
                  </div>
                  {postMode === "schedule" && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      className="mt-4 pt-4 border-t border-purple-500/20"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="block text-[10px] text-gray-400 mb-1">
                            Date
                          </label>
                          <input
                            type="date"
                            value={scheduleDate}
                            onChange={(e) => setScheduleDate(e.target.value)}
                            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-purple-500/50 transition-all [color-scheme:dark]"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] text-gray-400 mb-1">
                            Time
                          </label>
                          <input
                            type="time"
                            value={scheduleTime}
                            onChange={(e) => setScheduleTime(e.target.value)}
                            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white outline-none focus:border-purple-500/50 transition-all [color-scheme:dark]"
                          />
                        </div>
                      </div>
                    </motion.div>
                  )}
                </button>
              </div>

              {/* Navigation */}
              <div className="flex gap-3">
                <Button variant="secondary" onClick={prevStep} icon={<ArrowLeft className="w-4 h-4" />} size="lg">
                  Back
                </Button>
                <Button
                  onClick={handleConfirmPost}
                  loading={isPosting}
                  size="lg"
                  fullWidth
                  disabled={
                    postMode === "schedule" && (!scheduleDate || !scheduleTime)
                  }
                  icon={
                    postMode === "now" ? (
                      <Rocket className="w-4 h-4" />
                    ) : (
                      <CalendarDays className="w-4 h-4" />
                    )
                  }
                  iconPosition="right"
                >
                  {postMode === "now"
                    ? "Confirm & Post"
                    : "Confirm & Schedule"}
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </DashboardLayout>
  );
}

