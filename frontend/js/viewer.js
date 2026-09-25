/**
 * IRM Denoising Viewer - High-Performance Medical Viewport Engine
 */

export class MedicalViewer {
  constructor(canvasElement, options = {}) {
    this.canvas = canvasElement;
    this.ctx = canvasElement.getContext('2d', { alpha: false });
    this.options = Object.assign({
      isAiSlot: false,
      onStateChange: null,
      onSliceChange: null,
      onPixelProbe: null,
    }, options);

    // Transform State
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.invert = false;

    // Window / Level State
    this.windowCenter = null;
    this.windowWidth = null;
    this.defaultWc = null;
    this.defaultWw = null;

    // Active tool: 'wl' | 'pan' | 'zoom' | 'scroll'
    this.activeTool = 'wl';

    // Image Data
    this.currentImage = null;
    this.currentInstance = null;
    this.imageCache = new Map();
    this.hasInitialFit = false;

    // Interaction tracking
    this.isDragging = false;
    this.dragStartX = 0;
    this.dragStartY = 0;
    this.dragStartPanX = 0;
    this.dragStartPanY = 0;
    this.dragStartWc = 0;
    this.dragStartWw = 0;
    this.dragStartZoom = 1.0;

    // Synchronization callback
    this.syncPartner = null;
    this.isSyncing = false;

    this.initEvents();
    this.resizeCanvas();
  }

  getViewportDimensions() {
    const dpr = window.devicePixelRatio || 1;
    let cw = 0;
    let ch = 0;

    if (this.canvas && this.canvas.parentElement) {
      const rect = this.canvas.parentElement.getBoundingClientRect();
      if (rect.width > 50 && rect.height > 50) {
        cw = rect.width;
        ch = rect.height;
      }
    }

    if (ch <= 50) {
      const stage = document.getElementById('viewport-stage');
      if (stage) {
        const sRect = stage.getBoundingClientRect();
        if (sRect.width > 50 && sRect.height > 50) {
          cw = sRect.width;
          ch = sRect.height;
        }
      }
    }

    if (ch <= 50) {
      const headerH = 56;
      const toolbarH = 42;
      const footerH = 46;
      ch = Math.max(350, window.innerHeight - headerH - toolbarH - footerH);
      const leftW = document.getElementById('sidebar-left')?.offsetWidth || 280;
      cw = Math.max(350, window.innerWidth - leftW);
    }

    return { cw, ch, dpr };
  }

  resizeCanvas() {
    if (!this.canvas) return;
    const { cw, ch, dpr } = this.getViewportDimensions();
    if (cw <= 0 || ch <= 0) return;

    const newW = Math.round(cw * dpr);
    const newH = Math.round(ch * dpr);

    if (this.canvas.width !== newW || this.canvas.height !== newH) {
      this.canvas.width = newW;
      this.canvas.height = newH;
      this.render();
    }
  }

  initEvents() {
    window.addEventListener('resize', () => this.resizeCanvas());

    if (window.ResizeObserver && this.canvas && this.canvas.parentElement) {
      this.resizeObserver = new ResizeObserver(() => {
        const prevH = this.canvas.height;
        this.resizeCanvas();
        if (!this.hasInitialFit || prevH <= 200 || this.zoom < 0.6) {
          if (this.currentImage && this.currentImage.naturalWidth) {
            this.fitToWindow();
            this.hasInitialFit = true;
          }
        }
      });
      this.resizeObserver.observe(this.canvas.parentElement);
    }

    this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
    window.addEventListener('mousemove', (e) => this.onMouseMove(e));
    window.addEventListener('mouseup', () => this.onMouseUp());
    this.canvas.addEventListener('wheel', (e) => this.onWheel(e), { passive: false });
    this.canvas.addEventListener('dblclick', () => this.fitToWindow());
    this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());

    // Touch events for Mobile, Tablet & Touchscreen Laptops
    this.canvas.addEventListener('touchstart', (e) => this.onTouchStart(e), { passive: false });
    this.canvas.addEventListener('touchmove', (e) => this.onTouchMove(e), { passive: false });
    this.canvas.addEventListener('touchend', (e) => this.onTouchEnd(e), { passive: false });
    this.canvas.addEventListener('touchcancel', (e) => this.onTouchEnd(e), { passive: false });
  }

  setSyncPartner(partnerViewer) {
    this.syncPartner = partnerViewer;
  }

  setTool(toolName) {
    this.activeTool = toolName;
    if (this.canvas) {
      if (toolName === 'pan') this.canvas.style.cursor = 'grab';
      else if (toolName === 'zoom') this.canvas.style.cursor = 'zoom-in';
      else if (toolName === 'wl') this.canvas.style.cursor = 'crosshair';
      else if (toolName === 'scroll') this.canvas.style.cursor = 'ns-resize';
      else this.canvas.style.cursor = 'default';
    }
  }

  setPreset(presetKey) {
    const presets = {
      default: { wc: this.defaultWc, ww: this.defaultWw },
      lumbar_t2: { wc: 350, ww: 700 },
      lumbar_t1: { wc: 220, ww: 500 },
      stir: { wc: 280, ww: 600 },
      bone: { wc: 400, ww: 1200 },
      soft: { wc: 150, ww: 400 },
    };

    if (presets[presetKey]) {
      this.windowCenter = presets[presetKey].wc !== undefined ? presets[presetKey].wc : this.defaultWc;
      this.windowWidth = presets[presetKey].ww !== undefined ? presets[presetKey].ww : this.defaultWw;
      this.reloadInstanceImage();
      if (this.syncPartner && !this.isSyncing) {
        this.isSyncing = true;
        this.syncPartner.setPreset(presetKey);
        this.isSyncing = false;
      }
      this.notifyState();
    }
  }

  toggleInvert() {
    this.invert = !this.invert;
    this.reloadInstanceImage();
    if (this.syncPartner && !this.isSyncing) {
      this.isSyncing = true;
      this.syncPartner.invert = this.invert;
      this.syncPartner.reloadInstanceImage();
      this.isSyncing = false;
    }
    this.notifyState();
  }

  resetTransform() {
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.windowCenter = this.defaultWc;
    this.windowWidth = this.defaultWw;
    this.invert = false;
    this.reloadInstanceImage();
    this.fitToWindow();

    if (this.syncPartner && !this.isSyncing) {
      this.isSyncing = true;
      this.syncPartner.resetTransform();
      this.isSyncing = false;
    }
    this.notifyState();
  }

  fitToWindow() {
    if (!this.currentImage || !this.currentImage.naturalWidth) return;
    this.resizeCanvas();
    const { cw, ch } = this.getViewportDimensions();
    const iw = this.currentImage.naturalWidth;
    const ih = this.currentImage.naturalHeight;

    if (cw > 0 && ch > 0 && iw > 0 && ih > 0) {
      // Ajustement médical par défaut : remplit exactement 100% de la hauteur du visualiseur
      // pour que le rachis lombaire soit grand, net, centré et parfaitement cadré plein format
      const targetScale = (ch / ih);
      this.zoom = Math.max(0.6, Math.min(targetScale, 8.0));
      this.panX = 0;
      this.panY = 0;
      this.render();
    }

    if (this.syncPartner && !this.isSyncing) {
      this.isSyncing = true;
      this.syncPartner.zoom = this.zoom;
      this.syncPartner.panX = this.panX;
      this.syncPartner.panY = this.panY;
      this.syncPartner.render();
      this.isSyncing = false;
    }
    this.notifyState();
  }

  setZoomDelta(delta) {
    this.zoom = Math.max(0.2, Math.min(this.zoom + delta, 8.0));
    this.render();
    if (this.syncPartner && !this.isSyncing) {
      this.isSyncing = true;
      this.syncPartner.zoom = this.zoom;
      this.syncPartner.render();
      this.isSyncing = false;
    }
    this.notifyState();
  }

  clear() {
    this.currentInstance = null;
    this.currentImage = null;
    this.hasInitialFit = false;
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  async loadInstance(instanceData, forceReload = false, forceFit = false) {
    if (!instanceData) return;
    this.currentInstance = instanceData;

    if (this.defaultWc === null || forceReload || forceFit) {
      this.defaultWc = instanceData.window_center;
      this.defaultWw = instanceData.window_width;
      this.windowCenter = this.defaultWc;
      this.windowWidth = this.defaultWw;
    }

    await this.fetchAndDrawImage(forceReload);
    if (forceFit || !this.hasInitialFit) {
      this.fitToWindow();
      this.hasInitialFit = true;
    }
    this.notifyState();
  }

  async fetchAndDrawImage(forceReload = false) {
    if (!this.currentInstance) return;
    const instId = this.currentInstance.instance_uid || this.currentInstance.id;
    const endpoint = this.options.isAiSlot ? 'image_denoised' : 'image';
    
    let url = `/api/instances/${encodeURIComponent(instId)}/${endpoint}?invert=${this.invert}`;
    if (this.windowCenter !== null && this.windowWidth !== null && this.windowCenter !== undefined && this.windowWidth !== undefined) {
      url += `&wc=${Math.round(this.windowCenter)}&ww=${Math.round(this.windowWidth)}`;
    }

    const cacheKey = url;

    if (forceReload) {
      this.imageCache.delete(cacheKey);
      url += `&_t=${Date.now()}`;
    } else if (this.imageCache.has(cacheKey)) {
      this.currentImage = this.imageCache.get(cacheKey);
      if (!this.hasInitialFit) {
        this.fitToWindow();
        this.hasInitialFit = true;
      } else {
        this.render();
      }
      return;
    }

    this.loadError = false;
    const img = new Image();
    return new Promise((resolve) => {
      img.onload = () => {
        this.loadError = false;
        this.imageCache.set(cacheKey, img);
        this.currentImage = img;
        if (!this.hasInitialFit) {
          this.fitToWindow();
          this.hasInitialFit = true;
        } else {
          this.render();
        }
        resolve();
      };
      img.onerror = (e) => {
        console.error('Erreur chargement image DICOM:', url, e);
        this.loadError = true;
        this.render();
        resolve();
      };
      img.src = url;
    });
  }

  reloadInstanceImage() {
    this.fetchAndDrawImage(true);
  }

  onMouseDown(e) {
    this.isDragging = true;
    this.dragStartX = e.clientX;
    this.dragStartY = e.clientY;
    this.dragStartPanX = this.panX;
    this.dragStartPanY = this.panY;
    this.dragStartWc = this.windowCenter !== null ? this.windowCenter : 300;
    this.dragStartWw = this.windowWidth !== null ? this.windowWidth : 600;
    this.dragStartZoom = this.zoom;

    if (e.button === 1) {
      // Clic molette milieu = Pan direct
      this.dragTool = 'pan';
    } else if (e.button === 2) {
      // Clic droit = Zoom dynamique (ou WL si outil actif est Zoom)
      this.dragTool = (this.activeTool === 'wl') ? 'zoom' : 'wl';
    } else if (e.shiftKey) {
      // Shift + Clic gauche = Balayage direct des coupes
      this.dragTool = 'scroll';
    } else {
      this.dragTool = this.activeTool;
    }
  }

  onMouseMove(e) {
    if (!this.isDragging) return;

    const dx = e.clientX - this.dragStartX;
    const dy = e.clientY - this.dragStartY;

    if (this.dragTool === 'scroll') {
      // Balayage des coupes au curseur de souris (Stack Scroll)
      // Déplacement vertical : vers le bas = coupe suivante, vers le haut = coupe précédente
      const stepPixels = 10;
      const steps = Math.trunc(dy / stepPixels);
      if (steps !== 0) {
        this.dragStartY += steps * stepPixels;
        if (this.options.onSliceChange) {
          this.options.onSliceChange(steps);
        }
      }
    } else if (this.dragTool === 'pan') {
      this.panX = this.dragStartPanX + dx;
      this.panY = this.dragStartPanY + dy;
      this.render();

      if (this.syncPartner && !this.isSyncing) {
        this.isSyncing = true;
        this.syncPartner.panX = this.panX;
        this.syncPartner.panY = this.panY;
        this.syncPartner.render();
        this.isSyncing = false;
      }
      this.notifyState();
    } else if (this.dragTool === 'zoom') {
      const zoomFactor = Math.exp(-dy * 0.008);
      this.zoom = Math.max(0.2, Math.min(this.dragStartZoom * zoomFactor, 8.0));
      this.render();

      if (this.syncPartner && !this.isSyncing) {
        this.isSyncing = true;
        this.syncPartner.zoom = this.zoom;
        this.syncPartner.render();
        this.isSyncing = false;
      }
      this.notifyState();
    } else if (this.dragTool === 'wl') {
      const deltaWw = dx * 3;
      const deltaWc = -dy * 3;

      this.windowWidth = Math.max(1, Math.round(this.dragStartWw + deltaWw));
      this.windowCenter = Math.round(this.dragStartWc + deltaWc);

      this.reloadInstanceImage();

      if (this.syncPartner && !this.isSyncing) {
        this.isSyncing = true;
        this.syncPartner.windowWidth = this.windowWidth;
        this.syncPartner.windowCenter = this.windowCenter;
        this.syncPartner.reloadInstanceImage();
        this.isSyncing = false;
      }
      this.notifyState();
    }
  }

  onMouseUp() {
    this.isDragging = false;
  }

  onWheel(e) {
    e.preventDefault();

    // Si outil Zoom actif OU touche Ctrl/Alt pressée OU geste pinch trackpad
    if (this.activeTool === 'zoom' || e.ctrlKey || e.altKey) {
      const factor = e.deltaY < 0 ? 1.08 : 0.92;
      this.zoom = Math.max(0.2, Math.min(this.zoom * factor, 8.0));
      this.render();

      if (this.syncPartner && !this.isSyncing) {
        this.isSyncing = true;
        this.syncPartner.zoom = this.zoom;
        this.syncPartner.render();
        this.isSyncing = false;
      }
      this.notifyState();
    } else {
      // Changement / Balayage de coupe standard au défilement de molette
      const delta = e.deltaY < 0 ? -1 : 1;
      if (this.options.onSliceChange) {
        this.options.onSliceChange(delta);
      }
    }
  }

  // --- Support Tactile Avancé (Pinch-to-zoom & Multi-touch Pan) ---
  onTouchStart(e) {
    if (e.touches.length === 1) {
      // 1 doigt : action selon l'outil actif
      const t = e.touches[0];
      this.isDragging = true;
      this.dragStartX = t.clientX;
      this.dragStartY = t.clientY;
      this.dragStartPanX = this.panX;
      this.dragStartPanY = this.panY;
      this.dragStartWc = this.windowCenter !== null ? this.windowCenter : 300;
      this.dragStartWw = this.windowWidth !== null ? this.windowWidth : 600;
      this.dragStartZoom = this.zoom;
      this.dragTool = this.activeTool;
    } else if (e.touches.length === 2) {
      // 2 doigts : Pinch-to-zoom et Pan naturel
      e.preventDefault();
      this.isDragging = false;
      const t1 = e.touches[0];
      const t2 = e.touches[1];
      this.touchDistanceStart = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
      this.touchStartZoom = this.zoom;
      this.touchCenterStartX = (t1.clientX + t2.clientX) / 2;
      this.touchCenterStartY = (t1.clientY + t2.clientY) / 2;
      this.touchStartPanX = this.panX;
      this.touchStartPanY = this.panY;
    }
  }

  onTouchMove(e) {
    if (e.touches.length === 1 && this.isDragging) {
      e.preventDefault();
      const t = e.touches[0];
      const dx = t.clientX - this.dragStartX;
      const dy = t.clientY - this.dragStartY;

      if (this.dragTool === 'scroll') {
        const stepPixels = 12;
        const steps = Math.trunc(dy / stepPixels);
        if (steps !== 0) {
          this.dragStartY += steps * stepPixels;
          if (this.options.onSliceChange) {
            this.options.onSliceChange(steps);
          }
        }
      } else if (this.dragTool === 'pan') {
        this.panX = this.dragStartPanX + dx;
        this.panY = this.dragStartPanY + dy;
        this.render();
        if (this.syncPartner && !this.isSyncing) {
          this.isSyncing = true;
          this.syncPartner.panX = this.panX;
          this.syncPartner.panY = this.panY;
          this.syncPartner.render();
          this.isSyncing = false;
        }
        this.notifyState();
      } else if (this.dragTool === 'zoom') {
        const factor = Math.exp(-dy * 0.008);
        this.zoom = Math.max(0.2, Math.min(this.dragStartZoom * factor, 8.0));
        this.render();
        if (this.syncPartner && !this.isSyncing) {
          this.isSyncing = true;
          this.syncPartner.zoom = this.zoom;
          this.syncPartner.render();
          this.isSyncing = false;
        }
        this.notifyState();
      } else if (this.dragTool === 'wl') {
        this.windowWidth = Math.max(1, Math.round(this.dragStartWw + dx * 3));
        this.windowCenter = Math.round(this.dragStartWc - dy * 3);
        this.reloadInstanceImage();
        if (this.syncPartner && !this.isSyncing) {
          this.isSyncing = true;
          this.syncPartner.windowWidth = this.windowWidth;
          this.syncPartner.windowCenter = this.windowCenter;
          this.syncPartner.reloadInstanceImage();
          this.isSyncing = false;
        }
        this.notifyState();
      }
    } else if (e.touches.length === 2 && this.touchDistanceStart > 0) {
      // Pinch to zoom à 2 doigts
      e.preventDefault();
      const t1 = e.touches[0];
      const t2 = e.touches[1];
      const currentDist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
      const zoomRatio = currentDist / this.touchDistanceStart;
      this.zoom = Math.max(0.2, Math.min(this.touchStartZoom * zoomRatio, 8.0));

      // Pan à 2 doigts
      const currentCenterX = (t1.clientX + t2.clientX) / 2;
      const currentCenterY = (t1.clientY + t2.clientY) / 2;
      this.panX = this.touchStartPanX + (currentCenterX - this.touchCenterStartX);
      this.panY = this.touchStartPanY + (currentCenterY - this.touchCenterStartY);

      this.render();

      if (this.syncPartner && !this.isSyncing) {
        this.isSyncing = true;
        this.syncPartner.zoom = this.zoom;
        this.syncPartner.panX = this.panX;
        this.syncPartner.panY = this.panY;
        this.syncPartner.render();
        this.isSyncing = false;
      }
      this.notifyState();
    }
  }

  onTouchEnd(e) {
    if (e.touches.length === 0) {
      this.isDragging = false;
      this.touchDistanceStart = 0;
    } else if (e.touches.length === 1) {
      // Si un doigt est retiré, réinitialiser pour le doigt restant
      const t = e.touches[0];
      this.isDragging = true;
      this.dragStartX = t.clientX;
      this.dragStartY = t.clientY;
      this.dragStartPanX = this.panX;
      this.dragStartPanY = this.panY;
      this.dragStartZoom = this.zoom;
      this.touchDistanceStart = 0;
    }
  }

  render() {
    const dpr = window.devicePixelRatio || 1;
    const w = this.canvas.width;
    const h = this.canvas.height;

    if (w === 0 || h === 0) return;

    this.ctx.save();
    this.ctx.fillStyle = '#0a0e17';
    this.ctx.fillRect(0, 0, w, h);

    if (this.currentImage && this.currentImage.complete && this.currentImage.naturalWidth > 0) {
      this.ctx.translate(w / 2 + this.panX * dpr, h / 2 + this.panY * dpr);
      this.ctx.scale(this.zoom * dpr, this.zoom * dpr);

      const iw = this.currentImage.naturalWidth;
      const ih = this.currentImage.naturalHeight;

      this.ctx.imageSmoothingEnabled = false;
      this.ctx.drawImage(this.currentImage, -iw / 2, -ih / 2, iw, ih);
    } else if (this.loadError) {
      this.ctx.fillStyle = '#f87171';
      this.ctx.font = '13px JetBrains Mono, monospace';
      this.ctx.textAlign = 'center';
      this.ctx.fillText('Erreur de chargement - Cliquez pour réessayer', w / 2, h / 2);
    } else {
      this.ctx.fillStyle = '#94a3b8';
      this.ctx.font = '13px JetBrains Mono, monospace';
      this.ctx.textAlign = 'center';
      const msg = this.options.isAiSlot ? 'Débruitage IA en cours...' : 'Chargement de la coupe...';
      this.ctx.fillText(msg, w / 2, h / 2);
    }

    this.ctx.restore();
  }

  notifyState() {
    if (this.options.onStateChange) {
      this.options.onStateChange({
        zoom: this.zoom,
        panX: this.panX,
        panY: this.panY,
        windowCenter: this.windowCenter,
        windowWidth: this.windowWidth,
        invert: this.invert,
      });
    }
  }
}
