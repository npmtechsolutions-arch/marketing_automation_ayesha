import { create } from "zustand";

export interface Post {
  id: string;
  content: string;
  platforms: string[];
  status: "draft" | "scheduled" | "published" | "failed" | "pending_approval";
  scheduled_at?: string;
  published_at?: string;
  media_urls: string[];
  tags: string[];
  account_id: string;
  created_at: string;
  updated_at: string;
  metrics?: {
    likes: number;
    comments: number;
    shares: number;
    impressions: number;
    reach: number;
    engagement_rate: number;
  };
}

export type CalendarView = "month" | "week" | "day" | "agenda";

export interface ContentFilters {
  status?: string;
  platform?: string;
  dateRange?: { start: string; end: string };
  search?: string;
  tags?: string[];
}

interface ContentState {
  posts: Post[];
  selectedPost: Post | null;
  calendarView: CalendarView;
  filters: ContentFilters;
}

interface ContentActions {
  setPosts: (posts: Post[]) => void;
  selectPost: (post: Post | null) => void;
  setCalendarView: (view: CalendarView) => void;
  setFilters: (filters: ContentFilters) => void;
  addPost: (post: Post) => void;
  updatePost: (id: string, updates: Partial<Post>) => void;
  deletePost: (id: string) => void;
}

export const useContentStore = create<ContentState & ContentActions>((set) => ({
  posts: [],
  selectedPost: null,
  calendarView: "month",
  filters: {},

  setPosts: (posts: Post[]) =>
    set({ posts }),

  selectPost: (post: Post | null) =>
    set({ selectedPost: post }),

  setCalendarView: (view: CalendarView) =>
    set({ calendarView: view }),

  setFilters: (filters: ContentFilters) =>
    set({ filters }),

  addPost: (post: Post) =>
    set((state) => ({ posts: [post, ...state.posts] })),

  updatePost: (id: string, updates: Partial<Post>) =>
    set((state) => ({
      posts: state.posts.map((p) => (p.id === id ? { ...p, ...updates } : p)),
      selectedPost:
        state.selectedPost?.id === id
          ? { ...state.selectedPost, ...updates }
          : state.selectedPost,
    })),

  deletePost: (id: string) =>
    set((state) => ({
      posts: state.posts.filter((p) => p.id !== id),
      selectedPost: state.selectedPost?.id === id ? null : state.selectedPost,
    })),
}));
