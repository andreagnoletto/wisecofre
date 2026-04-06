/**
 * WiseAPI - Wrapper para chamadas à API do Wisecofre
 */
const WiseAPI = {
    getCSRFToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.content;
        const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
        return cookie ? cookie.split('=')[1] : '';
    },

    getAuthHeaders() {
        const token = localStorage.getItem('access_token');
        const headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCSRFToken(),
        };
        if (token) headers['Authorization'] = `Bearer ${token}`;
        return headers;
    },

    async request(method, url, body = null) {
        const opts = {
            method,
            headers: this.getAuthHeaders(),
            credentials: 'same-origin',
        };
        if (body) opts.body = JSON.stringify(body);

        const resp = await fetch(url, opts);

        if (resp.status === 401) {
            const refreshed = await this.refreshToken();
            if (refreshed) return this.request(method, url, body);
            window.location.href = '/admin/login/';
            throw new Error('Sessão expirada');
        }

        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            throw new Error(data.detail || `Erro ${resp.status}`);
        }

        if (resp.status === 204) return null;
        return resp.json();
    },

    get(url) { return this.request('GET', url); },
    post(url, body) { return this.request('POST', url, body); },
    put(url, body) { return this.request('PUT', url, body); },
    patch(url, body) { return this.request('PATCH', url, body); },
    delete(url) { return this.request('DELETE', url); },

    async refreshToken() {
        const refresh = localStorage.getItem('refresh_token');
        if (!refresh) return false;
        try {
            const resp = await fetch('/api/v1/auth/token/refresh/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh }),
            });
            if (!resp.ok) return false;
            const data = await resp.json();
            localStorage.setItem('access_token', data.access);
            if (data.refresh) localStorage.setItem('refresh_token', data.refresh);
            return true;
        } catch {
            return false;
        }
    },

    async uploadToPresigned(url, blob, onProgress) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('PUT', url);
            xhr.setRequestHeader('Content-Type', 'application/octet-stream');

            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable && onProgress) {
                    onProgress(Math.round((e.loaded / e.total) * 100));
                }
            });

            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) resolve();
                else reject(new Error(`Upload falhou: ${xhr.status}`));
            });

            xhr.addEventListener('error', () => reject(new Error('Erro de rede no upload')));
            xhr.send(blob);
        });
    },
};

/**
 * Utility: notify via toast
 */
function notify(message, type = 'info') {
    window.dispatchEvent(new CustomEvent('notify', { detail: { message, type } }));
}
