const APIClient = {
  unwrap(payload, httpStatus) {
    if (!payload || typeof payload !== 'object' || typeof payload.ok !== 'boolean') {
      throw new Error('Invalid API response envelope');
    }
    if (payload.ok) {
      if (!Object.prototype.hasOwnProperty.call(payload, 'data')) {
        throw new Error('Successful API response is missing data');
      }
      return payload.data;
    }
    const error = new Error(payload.message || payload.error || `HTTP ${httpStatus || payload.status || 500}`);
    error.name = 'ApiError';
    error.status = httpStatus || payload.status;
    error.body = payload;
    throw error;
  },

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
    const data = this.unwrap(await response.json(), response.status);
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
