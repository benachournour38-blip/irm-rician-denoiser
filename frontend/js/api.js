/**
 * IRM Denoising Viewer - API Client avec Authentification Sécurisée
 */

const API_BASE = '';
const TOKEN_KEY = 'mri_viewer_auth_token';

export const API = {
  getAuthToken() {
    // Session ephemeral : détruite dès la fermeture de l'onglet/fenêtre
    return sessionStorage.getItem(TOKEN_KEY) || '';
  },

  setAuthToken(token) {
    sessionStorage.setItem(TOKEN_KEY, token);
    localStorage.removeItem(TOKEN_KEY); // Sécurité : pas de persistance inter-fenêtres
  },

  clearAuthToken() {
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_KEY);
  },

  async authFetch(url, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    const token = this.getAuthToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    headers['ngrok-skip-browser-warning'] = 'true';
    options.headers = headers;

    const res = await fetch(url, options);
    if (res.status === 401) {
      this.clearAuthToken();
      window.dispatchEvent(new CustomEvent('auth:unauthorized'));
    }
    return res;
  },

  async login(password) {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true'
      },
      body: JSON.stringify({ password })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'Mot de passe incorrect');
    }
    this.setAuthToken(data.token, true);
    return data;
  },

  async verifyAuth() {
    const token = this.getAuthToken();
    if (!token) return null;
    try {
      const res = await this.authFetch(`${API_BASE}/api/auth/me`);
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  },

  async logout() {
    try {
      await this.authFetch(`${API_BASE}/api/auth/logout`, { method: 'POST' });
    } catch {}
    this.clearAuthToken();
  },

  async getPatients(query = '') {
    const url = query ? `${API_BASE}/api/patients?q=${encodeURIComponent(query)}` : `${API_BASE}/api/patients`;
    const res = await this.authFetch(url);
    if (!res.ok) throw new Error(`Erreur récupération patients: ${res.statusText}`);
    return await res.json();
  },

  async getPatient(patientId) {
    const res = await this.authFetch(`${API_BASE}/api/patients/${encodeURIComponent(patientId)}`);
    if (!res.ok) throw new Error(`Patient non trouvé: ${res.statusText}`);
    return await res.json();
  },

  async deletePatient(patientId) {
    const res = await this.authFetch(`${API_BASE}/api/patients/${encodeURIComponent(patientId)}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error(`Erreur suppression patient: ${res.statusText}`);
    return await res.json();
  },

  async getPatientStudies(patientId) {
    const res = await this.authFetch(`${API_BASE}/api/patients/${encodeURIComponent(patientId)}/studies`);
    if (!res.ok) throw new Error(`Erreur récupération examens: ${res.statusText}`);
    return await res.json();
  },

  async getStudySeries(studyUid) {
    const res = await this.authFetch(`${API_BASE}/api/studies/${encodeURIComponent(studyUid)}/series`);
    if (!res.ok) throw new Error(`Erreur récupération séries: ${res.statusText}`);
    return await res.json();
  },

  async getSeriesDetail(seriesUid) {
    const res = await this.authFetch(`${API_BASE}/api/series/${encodeURIComponent(seriesUid)}`);
    if (!res.ok) throw new Error(`Erreur détails série: ${res.statusText}`);
    return await res.json();
  },

  async getSeriesInstances(seriesUid) {
    const res = await this.authFetch(`${API_BASE}/api/series/${encodeURIComponent(seriesUid)}/instances`);
    if (!res.ok) throw new Error(`Erreur coupes: ${res.statusText}`);
    return await res.json();
  },

  async getInstanceMetadata(instanceUid) {
    const res = await this.authFetch(`${API_BASE}/api/instances/${encodeURIComponent(instanceUid)}/metadata`);
    if (!res.ok) throw new Error(`Erreur métadonnées: ${res.statusText}`);
    return await res.json();
  },

  async getInstanceMetrics(instanceUid) {
    const res = await this.authFetch(`${API_BASE}/api/instances/${encodeURIComponent(instanceUid)}/metrics`);
    if (!res.ok) throw new Error(`Erreur métriques: ${res.statusText}`);
    return await res.json();
  },

  getExportSeriesDenoisedUrl(seriesUid) {
    const token = this.getAuthToken();
    return `${API_BASE}/api/series/${encodeURIComponent(seriesUid)}/export_denoised?token=${encodeURIComponent(token)}`;
  },

  getExportDenoisedDicomUrl(instanceUid) {
    const token = this.getAuthToken();
    return `${API_BASE}/api/instances/${encodeURIComponent(instanceUid)}/dicom_denoised?token=${encodeURIComponent(token)}`;
  },

  getInstanceImageUrl(instanceUid, wc = null, ww = null, invert = false) {
    let url = `${API_BASE}/api/instances/${encodeURIComponent(instanceUid)}/image?invert=${invert}`;
    if (wc !== null && ww !== null) {
      url += `&wc=${wc}&ww=${ww}`;
    }
    return url;
  },

  getInstanceDenoisedImageUrl(instanceUid, wc = null, ww = null, invert = false) {
    let url = `${API_BASE}/api/instances/${encodeURIComponent(instanceUid)}/image_denoised?invert=${invert}`;
    if (wc !== null && ww !== null) {
      url += `&wc=${wc}&ww=${ww}`;
    }
    return url;
  },

  async getAiStatus() {
    const res = await this.authFetch(`${API_BASE}/api/denoise/status`);
    if (!res.ok) throw new Error(`Erreur statut IA: ${res.statusText}`);
    return await res.json();
  },

  async uploadFiles(fileList, onProgress = null) {
    const formData = new FormData();
    for (let i = 0; i < fileList.length; i++) {
      formData.append('files', fileList[i]);
    }

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/api/dicom/upload`, true);

      const token = this.getAuthToken();
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      }

      if (onProgress && xhr.upload) {
        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            const pct = Math.round((e.loaded / e.total) * 100);
            onProgress(pct);
          }
        };
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText));
          } catch (e) {
            resolve({ message: 'Fichiers importés avec succès' });
          }
        } else {
          try {
            const errJson = JSON.parse(xhr.responseText);
            reject(new Error(errJson.detail || `Erreur ${xhr.status}`));
          } catch {
            reject(new Error(`Erreur serveur (${xhr.status})`));
          }
        }
      };

      xhr.onerror = () => reject(new Error('Erreur de connexion réseau'));
      xhr.send(formData);
    });
  }
};
