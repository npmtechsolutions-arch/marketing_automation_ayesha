import { create } from "zustand";
import api, { refreshAccessToken } from "@/lib/api";
import { useUIStore } from "./uiStore";

export interface User {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string;
  role: string;
  // Gates the /admin routes. The API sends this; `role` it never has, which
  // is why the admin panel used to be unreachable.
  is_superadmin?: boolean;
  is_active: boolean;
  two_factor_enabled?: boolean;
  preferences?: Record<string, any> | null;
  created_at: string;
}

interface AuthState {
  user: User | null;
  // Memory only. Never written to localStorage: a token sitting in storage
  // outlives the tab and can be read back by any script that runs on the page.
  accessToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  // False until bootstrap() has had its turn, so guards can tell "signed out"
  // apart from "we have not asked yet" and avoid bouncing to /login on reload.
  isBootstrapped: boolean;

  // The active tenant. Previously the workspace id lived only in localStorage,
  // so nothing re-rendered when it changed and a switch was invisible to React.
  organizations: Organization[];
  workspaces: Workspace[];
  activeOrgId: string | null;
  activeWorkspaceId: string | null;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  subscription_tier: string;
  // No limits here. They are not serialized on the organization any more --
  // GET /organizations/{id}/usage reports them, resolved the same way
  // enforcement resolves them.
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  organization_id: string;
  /** The caller's role in this workspace. Owners report "owner". */
  role?: string | null;
  /** The owning organization's name, for grouping in the switcher.
   *
   *  Sent by /accounts so a workspace can be grouped without the caller being
   *  an organization member -- which an invited collaborator is not. */
  organization_name?: string | null;
}

export interface LoginResult {
  requires2fa: boolean;
  challengeToken?: string;
}

interface AuthActions {
  login: (email: string, password: string) => Promise<LoginResult>;
  complete2faLogin: (challengeToken: string, code: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
  bootstrap: () => Promise<void>;
  setSession: (accessToken: string, user: User | null) => void;
  clearSession: () => void;
  setUser: (user: User) => void;
  loadUser: () => Promise<void>;
  loadTenants: () => Promise<void>;
  switchWorkspace: (workspaceId: string) => void;
}

// A marker saying a session probably exists, so an anonymous visitor is not
// made to fire a doomed refresh on every first page load.
//
// It carries no secret and grants nothing: the refresh still requires the
// httpOnly cookie, which JavaScript cannot read or forge. All this decides is
// whether it is worth *asking*. An attacker who sets it gets a 401 instead of
// a skipped call, which is what an anonymous visitor was already getting --
// only noisily, in everyone's console, on the public landing page.
const SESSION_HINT_KEY = "has_session";

function rememberSession(exists: boolean): void {
  try {
    if (exists) localStorage.setItem(SESSION_HINT_KEY, "1");
    else localStorage.removeItem(SESSION_HINT_KEY);
  } catch {
    // Private browsing, or storage disabled. The cost is the old behaviour:
    // one failed refresh per load, which is noise rather than breakage.
  }
}

function sessionLikely(): boolean {
  try {
    return localStorage.getItem(SESSION_HINT_KEY) === "1";
  } catch {
    // Cannot tell, so assume yes: a spurious 401 is better than refusing to
    // restore a session that is genuinely there.
    return true;
  }
}

export function syncUserPreferences(user: User | null): void {
  if (!user?.preferences) return;
  const app = user.preferences.appearance;
  if (app) {
    if (app.sidebar) {
      const isCollapsed = app.sidebar === "collapsed";
      localStorage.setItem("sidebar_collapsed", String(isCollapsed));
      useUIStore.getState().setSidebarCollapsed(isCollapsed);
    }
    if (app.calendarView) {
      localStorage.setItem("calendar_default_view", app.calendarView);
    }
    if (app.theme === "dark" || app.theme === "light") {
      useUIStore.getState().setTheme(app.theme);
    }
  }
}

// The key the chosen workspace is remembered under. It is a preference, not a
// credential: the backend authorises every request against the workspace in the
// URL regardless of what is stored here.
const ACTIVE_WORKSPACE_KEY = "account_id";
const ACTIVE_ORG_KEY = "organization_id";

function readStored(key: string): string | null {
  try {
    const value = localStorage.getItem(key);
    return value && value !== "null" && value !== "undefined" ? value : null;
  } catch {
    return null; // private mode, or storage disabled
  }
}

function writeStored(key: string, value: string | null): void {
  try {
    if (value) localStorage.setItem(key, value);
    else localStorage.removeItem(key);
  } catch {
    /* preference only -- losing it is not worth failing a sign-in over */
  }
}

/** Unwrap the several response shapes these endpoints return.
 *
 *  Four shapes are in play, because `api` here is the raw axios instance (the
 *  `get`/`post` helpers in lib/api unwrap `.data`, the default export does
 *  not), and because `/accounts` is paginated while `/organizations/` returns
 *  a bare array:
 *
 *    [...]                        a bare array
 *    { items: [...] }             an unwrapped paginated body
 *    { data: { items: [...] } }   an axios response around one
 *    { data: [...] }              an axios response around a bare array
 *
 *  The last was missing, and it is exactly the shape `/organizations/`
 *  produces. `organizations` was therefore *always* empty, and the workspace
 *  switcher -- which iterates organizations and hangs workspaces beneath them
 *  -- listed nothing for anyone, ever. The account list worked, so the store
 *  looked fine; only the dropdown was blank, which read as a styling bug.
 */
function itemsOf(response: any): any[] {
  if (Array.isArray(response)) return response;
  if (Array.isArray(response?.data)) return response.data;
  return response?.items ?? response?.data?.items ?? [];
}

export const useAuthStore = create<AuthState & AuthActions>((set, get) => ({
  user: null,
  // Nothing is restored synchronously; bootstrap() re-establishes the session
  // from the httpOnly refresh cookie on load.
  accessToken: null,
  isAuthenticated: false,
  isLoading: false,
  isBootstrapped: false,
  organizations: [],
  workspaces: [],
  activeOrgId: null,
  activeWorkspaceId: null,

  login: async (email: string, password: string) => {
    set({ isLoading: true });
    try {
      const { data } = await api.post("/auth/login", { email, password });

      // Account has 2FA enabled — caller must complete the challenge.
      if (data.requires_2fa) {
        set({ isLoading: false });
        return { requires2fa: true, challengeToken: data.challenge_token };
      }

      const { access_token, user } = data;
      // The refresh token came back as an httpOnly cookie; the body copy is
      // ignored so it never lands anywhere a script can read.
      set({ user, accessToken: access_token, isAuthenticated: true, isBootstrapped: true });
      await get().loadTenants();

      syncUserPreferences(user);
      set({ isLoading: false });
      return { requires2fa: false };
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  complete2faLogin: async (challengeToken: string, code: string) => {
    set({ isLoading: true });
    try {
      const { data } = await api.post("/auth/login/2fa", {
        challenge_token: challengeToken,
        code,
      });
      const { access_token, user } = data;
      set({ user, accessToken: access_token, isAuthenticated: true, isBootstrapped: true });
      await get().loadTenants();

      syncUserPreferences(user);
      set({ isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  register: async (email: string, password: string, fullName: string) => {
    set({ isLoading: true });
    try {
      const { data } = await api.post("/auth/register", {
        email,
        password,
        full_name: fullName,
      });
      const { access_token, user } = data;
      set({ user, accessToken: access_token, isAuthenticated: true, isBootstrapped: true });

      // Fetch user's first account
      try {
        const accountsResponse: any = await api.get("/accounts");
        let accountId = null;

        // Handle different response formats
        if (accountsResponse.items?.[0]?.id) {
          accountId = accountsResponse.items[0].id;
        } else if (accountsResponse.data?.items?.[0]?.id) {
          accountId = accountsResponse.data.items[0].id;
        } else if (Array.isArray(accountsResponse) && accountsResponse[0]?.id) {
          accountId = accountsResponse[0].id;
        }

        if (accountId) {
          localStorage.setItem("account_id", accountId);
          console.log("Stored account_id:", accountId);
        } else {
          console.warn("No account found in response:", accountsResponse);
        }
      } catch (err) {
        console.warn("Could not fetch accounts:", err);
      }

      syncUserPreferences(user);
      set({ isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      throw error;
    }
  },

  logout: async () => {
    // Tell the backend first so the UserSession is actually revoked and the
    // refresh cookie cleared -- dropping local state alone would leave the
    // session usable by anyone holding the cookie.
    try {
      await api.post("/auth/logout");
    } catch {
      // Already signed out, offline, or the token expired. Clearing locally is
      // still the right outcome.
    }
    get().clearSession();
  },

  setSession: (accessToken: string, user: User | null) => {
    set((state) => ({
      accessToken,
      user: user ?? state.user,
      isAuthenticated: true,
      isBootstrapped: true,
    }));
    if (user) syncUserPreferences(user);
  },

  clearSession: () => {
    writeStored(ACTIVE_WORKSPACE_KEY, null);
    writeStored(ACTIVE_ORG_KEY, null);
    set({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      isBootstrapped: true,
      organizations: [],
      workspaces: [],
      activeOrgId: null,
      activeWorkspaceId: null,
    });
  },

  // Called once on app load. There is no token in storage to read any more, so
  // the only way to know whether a session survives a reload is to ask: if the
  // httpOnly refresh cookie is still valid the backend returns a fresh access
  // token, otherwise this is simply a signed-out visitor.
  bootstrap: async () => {
    if (get().isBootstrapped) return;

    // No sign of a session, so do not ask. This used to fire on the public
    // landing page for every anonymous visitor, producing a failed request and
    // a console error on a first visit -- which also trained us to ignore a
    // console error that later turned out to be the S1 refresh bug.
    if (!sessionLikely()) {
      set({ isBootstrapped: true, isAuthenticated: false });
      return;
    }

    set({ isLoading: true });
    try {
      const accessToken = await refreshAccessToken();
      set({ accessToken, isAuthenticated: true });
      await get().loadUser();
      await get().loadTenants();
    } catch {
      // The cookie is gone or expired. Forget the hint so the next load is
      // quiet rather than repeating this.
      rememberSession(false);
      set({ user: null, accessToken: null, isAuthenticated: false });
    } finally {
      set({ isLoading: false, isBootstrapped: true });
    }
  },

  // Load the organizations and workspaces the user can reach, and settle on an
  // active one.
  //
  // The stored choice is VALIDATED and kept rather than overwritten. The old
  // resolveAccountId() unconditionally wrote items[0].id on every load, which
  // would have silently undone a user's switch on every page refresh.
  loadTenants: async () => {
    try {
      const [orgsResponse, workspacesResponse] = await Promise.all([
        api.get("/organizations/"),
        api.get("/accounts"),
      ]);
      const organizations = itemsOf(orgsResponse) as Organization[];
      const workspaces = itemsOf(workspacesResponse) as Workspace[];

      const stored = readStored(ACTIVE_WORKSPACE_KEY);
      const active =
        workspaces.find((w) => w.id === stored) ?? workspaces[0] ?? null;
      const storedOrg = readStored(ACTIVE_ORG_KEY);
      const activeOrg =
        organizations.find((o) => o.id === (active?.organization_id ?? storedOrg)) ??
        organizations[0] ??
        null;

      writeStored(ACTIVE_WORKSPACE_KEY, active?.id ?? null);
      writeStored(ACTIVE_ORG_KEY, activeOrg?.id ?? null);
      set({
        organizations,
        workspaces,
        activeWorkspaceId: active?.id ?? null,
        activeOrgId: activeOrg?.id ?? null,
      });
    } catch (err) {
      console.warn("Could not load organizations/workspaces:", err);
    }
  },

  switchWorkspace: (workspaceId: string) => {
    const { workspaces, activeWorkspaceId } = get();
    if (workspaceId === activeWorkspaceId) return;
    const target = workspaces.find((w) => w.id === workspaceId);
    if (!target) return;

    writeStored(ACTIVE_WORKSPACE_KEY, target.id);
    writeStored(ACTIVE_ORG_KEY, target.organization_id);
    // Pages read the workspace id at mount and cache it in local state, so the
    // router outlet is keyed on this value: changing it remounts them and every
    // request goes to the new workspace. See App.tsx.
    set({
      activeWorkspaceId: target.id,
      activeOrgId: target.organization_id,
    });
  },

  setUser: (user: User) => {
    syncUserPreferences(user);
    set({ user });
  },

  loadUser: async () => {
    const { accessToken } = get();
    if (!accessToken) return;

    set({ isLoading: true });
    try {
      const { data } = await api.get("/users/me");
      
      let accountId = localStorage.getItem("account_id");
      if (!accountId) {
        try {
          const accountsResponse: any = await api.get("/accounts");
          if (accountsResponse.items?.[0]?.id) {
            accountId = accountsResponse.items[0].id;
          } else if (accountsResponse.data?.items?.[0]?.id) {
            accountId = accountsResponse.data.items[0].id;
          } else if (Array.isArray(accountsResponse) && accountsResponse[0]?.id) {
            accountId = accountsResponse[0].id;
          }
          if (accountId) {
            localStorage.setItem("account_id", accountId);
          }
        } catch (err) {
          console.warn("Could not fetch accounts in loadUser:", err);
        }
      }

      syncUserPreferences(data);
      set({ user: data, isAuthenticated: true, isLoading: false });
    } catch (error: any) {
      set({ isLoading: false });
      if (error?.response?.status === 401) {
        // The axios interceptor already tried to refresh. Clear locally rather
        // than calling logout(), which would revoke a session that may still
        // be perfectly valid.
        get().clearSession();
      }
    }
  },
}));

// Keep the hint in step with the store, rather than asking every sign-in path
// to remember it.
//
// The first version of this called rememberSession(true) inside setSession() --
// and both login() and register() build their state with a direct set(), so
// neither ever reached it. The marker stayed absent, bootstrap skipped the
// refresh, and reloading any page signed you out: the exact S1 the refresh fix
// had just cured, reintroduced by its own follow-up. Subscribing to the flag
// means a new path cannot forget.
useAuthStore.subscribe((state, previous) => {
  if (state.isAuthenticated !== previous.isAuthenticated) {
    rememberSession(state.isAuthenticated);
  }
});
