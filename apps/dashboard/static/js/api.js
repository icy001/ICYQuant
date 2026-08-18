/* ICYQuant Dashboard - API client.
 * Talks to the Backend API gateway only (Authorization: Bearer). */
(function (global) {
  "use strict";

  const TOKEN_KEY = "icy_dash_token";
  const USER_KEY = "icy_dash_user";

  const API = {
    _token: localStorage.getItem(TOKEN_KEY) || null,
    _user: null,

    get user() {
      if (!this._user) {
        try {
          this._user = JSON.parse(localStorage.getItem(USER_KEY) || "null");
        } catch (e) {
          this._user = null;
        }
      }
      return this._user;
    },

    isAuthenticated() {
      return !!this._token;
    },

    _save(token, user) {
      this._token = token;
      this._user = user;
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
      if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
      else localStorage.removeItem(USER_KEY);
    },

    async request(path, opts) {
      opts = opts || {};
      const headers = { "Content-Type": "application/json" };
      if (this._token) headers["Authorization"] = "Bearer " + this._token;
      const res = await fetch("/api" + path, {
        method: opts.method || "GET",
        headers,
        body: opts.body ? JSON.stringify(opts.body) : undefined,
      });
      if (res.status === 401) {
        this._save(null, null);
        throw Object.assign(new Error("Unauthorized"), { status: 401 });
      }
      let data = null;
      try {
        data = await res.json();
      } catch (e) {
        /* empty body */
      }
      if (!res.ok) {
        const detail =
          (data && data.detail) || res.statusText || "Request failed";
        throw Object.assign(new Error(detail), { status: res.status });
      }
      return data;
    },

    async login(username, password) {
      const data = await this.request("/auth/login", {
        method: "POST",
        body: { username, password },
      });
      this._save(data.token, data.user);
      return data;
    },

    async logout() {
      try {
        await this.request("/auth/logout", { method: "POST" });
      } catch (e) {
        /* ignore network errors on logout */
      }
      this._save(null, null);
    },

    get(path) {
      return this.request(path);
    },
    post(path, body) {
      return this.request(path, { method: "POST", body });
    },
  };

  global.ICY_API = API;
})(window);
