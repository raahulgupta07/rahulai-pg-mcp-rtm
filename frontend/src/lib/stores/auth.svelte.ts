import { goto } from '$app/navigation';

const TOKEN_KEY = 'rtm_token';
const USER_KEY = 'rtm_user';

interface User {
  id: number;
  username: string;
  role: string;
  display_name: string;
}

class AuthStore {
  token = $state<string | null>(null);
  user = $state<User | null>(null);

  isAuthenticated = $derived(!!this.token && !!this.user);
  isAdmin = $derived(this.user?.role === 'admin');

  constructor() {
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem(TOKEN_KEY);
      const saved = localStorage.getItem(USER_KEY);
      if (saved) try { this.user = JSON.parse(saved); } catch { this.user = null; }
    }
  }

  login(token: string, user: User) {
    this.token = token;
    this.user = user;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  logout() {
    this.token = null;
    this.user = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    goto('/login');
  }

  getHeaders(): Record<string, string> {
    return this.token ? { 'Authorization': `Bearer ${this.token}` } : {};
  }
}

export const auth = new AuthStore();
