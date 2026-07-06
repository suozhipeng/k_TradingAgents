const APIClient = {
  buildUrl(path, params = {}) {
    const url = new URL(path, window.location.origin);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    });
    return url.toString();
  },

  async fetchJson(path, options = {}) {
    const response = await fetch(path, options);
    const data = await response.json();
    return { response, data };
  },

  async getJson(path, params = {}, options = {}) {
    return this.fetchJson(this.buildUrl(path, params), options);
  },

  async postJson(path, payload, options = {}) {
    return this.fetchJson(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      body: JSON.stringify(payload),
      ...options,
    });
  },
};

window.APIClient = APIClient;
