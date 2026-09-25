/**
 * IRM Denoising Viewer - Application Main Controller
 */

import { API } from './api.js?v=1.1.1';
import { MedicalViewer } from './viewer.js?v=1.1.4';

class AppController {
  constructor() {
    this.state = {
      patients: [],
      currentPatient: null,
      currentStudy: null,
      currentSeries: null,
      instances: [],
      currentSliceIndex: 0,
      viewMode: 'original', // 'original' | 'denoised' | 'compare_split' | 'curtain'
      isSync: true,
      isAnonymized: false,
      isCinePlaying: false,
      cineFps: 10,
      cineTimer: null,
      activeTool: 'wl',
      curtainPos: 50, // percent
      currentUser: null,
    };

    this.viewerOriginal = null;
    this.viewerAi = null;
    this.curtainOriginalViewer = null;

    this.init();
  }

  async init() {
    this.bindDOMElements();
    this.initViewers();
    this.bindEvents();
    this.bindAuthEvents();
    this.bindKeyboardShortcuts();
    
    // Check Authentication First
    await this.checkAuthentication();
  }

  bindDOMElements() {
    // Canvas Elements
    this.canvasOriginal = document.getElementById('canvas-original');
    this.canvasAi = document.getElementById('canvas-ai');
    this.canvasCurtainOriginal = document.getElementById('canvas-curtain-orig');
    this.canvasCurtainDenoised = document.getElementById('canvas-curtain-denoised');

    // Containers
    this.viewportsWrapper = document.getElementById('viewports-wrapper');
    this.viewportPanelOriginal = document.getElementById('viewport-panel-original');
    this.viewportPanelAi = document.getElementById('viewport-panel-ai');
    this.curtainContainer = document.getElementById('curtain-container');
    this.curtainHandle = document.getElementById('curtain-handle');
    this.curtainTopLayer = document.getElementById('curtain-top-layer');

    // UI Elements (Left Sidebar)
    this.sidebarLeft = document.getElementById('sidebar-left');
    this.btnCollapseSidebarLeft = document.getElementById('btn-collapse-sidebar-left');
    this.btnExpandSidebarLeft = document.getElementById('btn-expand-sidebar-left');
    this.btnTogglePatientsToolbar = document.getElementById('btn-toggle-patients-toolbar');
    this.patientListContainer = document.getElementById('patient-list-container');
    this.patientSearchInput = document.getElementById('patient-search-input');
    this.sliceSlider = document.getElementById('slice-slider');
    this.sliceDisplay = document.getElementById('slice-display');
    this.sliceLocationDisplay = document.getElementById('slice-location-display');
    this.btnPrevSlice = document.getElementById('btn-prev-slice');
    this.btnNextSlice = document.getElementById('btn-next-slice');
    this.btnCinePlay = document.getElementById('btn-cine-play');
    this.btnSync = document.getElementById('btn-sync-viewers');
    this.anonymizeToggle = document.getElementById('toggle-anonymize');

    // Header context tags
    this.headerPatientName = document.getElementById('header-patient-name');
    this.headerStudyDesc = document.getElementById('header-study-desc');
    this.headerSeriesDesc = document.getElementById('header-series-desc');
    this.btnCloseExam = document.getElementById('btn-close-exam');

    // Empty Viewport Placeholder
    this.viewportEmptyPlaceholder = document.getElementById('viewport-empty-placeholder');
    this.btnEmptyUpload = document.getElementById('btn-empty-upload');

    // Metadata Panel
    this.sidebarRight = document.getElementById('sidebar-right');
    this.metadataContent = document.getElementById('metadata-content');
    this.btnAllMetadata = document.getElementById('btn-all-metadata');
    this.btnCollapseSidebarRight = document.getElementById('btn-collapse-sidebar-right');
    this.btnExpandSidebarRight = document.getElementById('btn-expand-sidebar-right');
    this.btnToggleMetaToolbar = document.getElementById('btn-toggle-meta-toolbar');

    // Modals
    this.uploadModal = document.getElementById('upload-modal');
    this.btnOpenUpload = document.getElementById('btn-open-upload');
    this.btnOpenUploadSidebar = document.getElementById('btn-open-upload-sidebar');
    this.btnCloseUpload = document.getElementById('btn-close-upload');
    this.dropzone = document.getElementById('upload-dropzone');
    this.fileInput = document.getElementById('file-input');
    this.folderInput = document.getElementById('folder-input');
    this.uploadProgress = document.getElementById('upload-progress');
    this.uploadProgressFill = document.getElementById('upload-progress-fill');
    this.uploadStatusText = document.getElementById('upload-status-text');

    this.metadataModal = document.getElementById('metadata-modal');
    this.btnCloseMetadata = document.getElementById('btn-close-metadata');
    this.metadataTagsBody = document.getElementById('metadata-tags-body');
    this.tagSearchInput = document.getElementById('tag-search-input');

    this.shortcutsModal = document.getElementById('shortcuts-modal');
    this.btnOpenShortcuts = document.getElementById('btn-open-shortcuts');
    this.btnCloseShortcuts = document.getElementById('btn-close-shortcuts');

    this.aiInfoModal = document.getElementById('ai-info-modal');
    this.btnCloseAiInfo = document.getElementById('btn-close-ai-info');

    // Auth Portal Elements
    this.loginPortal = document.getElementById('login-portal');
    this.loginForm = document.getElementById('login-form');
    this.loginPasswordInput = document.getElementById('login-password');
    this.loginErrorMsg = document.getElementById('login-error-msg');
    this.btnTogglePwd = document.getElementById('btn-toggle-pwd');
    this.btnSubmitLogin = document.getElementById('btn-submit-login');
    this.btnLogout = document.getElementById('btn-logout');
    this.userNameDisplay = document.getElementById('user-name-display');
  }

  async checkAuthentication() {
    try {
      const authRes = await API.verifyAuth();
      if (authRes && authRes.authenticated) {
        this.state.currentUser = authRes.user;
        if (this.userNameDisplay) {
          this.userNameDisplay.textContent = authRes.user.username || 'Dr. Radiologue';
        }
        if (this.loginPortal) {
          this.loginPortal.classList.add('hidden');
        }
        await this.loadPatients();
      } else {
        if (this.loginPortal) {
          this.loginPortal.classList.remove('hidden');
        }
      }
    } catch {
      if (this.loginPortal) {
        this.loginPortal.classList.remove('hidden');
      }
    }
  }

  bindAuthEvents() {
    // Show/Hide Password
    if (this.btnTogglePwd && this.loginPasswordInput) {
      this.btnTogglePwd.addEventListener('click', () => {
        const isPwd = this.loginPasswordInput.type === 'password';
        this.loginPasswordInput.type = isPwd ? 'text' : 'password';
        const eyeOpen = this.btnTogglePwd.querySelector('.icon-eye-open');
        const eyeClosed = this.btnTogglePwd.querySelector('.icon-eye-closed');
        if (eyeOpen && eyeClosed) {
          eyeOpen.style.display = isPwd ? 'block' : 'none';
          eyeClosed.style.display = isPwd ? 'none' : 'block';
        }
      });
    }

    // Login Form Submit
    if (this.loginForm) {
      this.loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const pwd = this.loginPasswordInput.value;
        if (!pwd) return;

        this.btnSubmitLogin.disabled = true;
        this.btnSubmitLogin.innerHTML = `<span>Connexion en cours...</span>`;
        if (this.loginErrorMsg) this.loginErrorMsg.style.display = 'none';

        try {
          const res = await API.login(pwd);
          this.state.currentUser = res.user;
          if (this.userNameDisplay) {
            this.userNameDisplay.textContent = res.user.username;
          }
          this.loginPasswordInput.value = '';
          this.loginPortal.classList.add('hidden');
          setTimeout(() => {
            window.dispatchEvent(new Event('resize'));
            if (this.viewerOriginal) this.viewerOriginal.fitToWindow();
            if (this.viewerAi) this.viewerAi.fitToWindow();
          }, 360);
          await this.loadPatients();
        } catch (err) {
          if (this.loginErrorMsg) {
            this.loginErrorMsg.textContent = err.message || 'Mot de passe incorrect';
            this.loginErrorMsg.style.display = 'block';
          }
        } finally {
          this.btnSubmitLogin.disabled = false;
          this.btnSubmitLogin.innerHTML = `<span>Connexion</span>`;
        }
      });
    }

    // Logout Button
    if (this.btnLogout) {
      this.btnLogout.addEventListener('click', async () => {
        if (confirm('Voulez-vous verrouiller la station et vous déconnecter ?')) {
          await API.logout();
          this.state.currentUser = null;
          if (this.loginPortal) {
            this.loginPortal.classList.remove('hidden');
            if (this.loginPasswordInput) this.loginPasswordInput.focus();
          }
        }
      });
    }

    // Unauthorized Event Handler
    window.addEventListener('auth:unauthorized', () => {
      this.state.currentUser = null;
      if (this.loginPortal) {
        this.loginPortal.classList.remove('hidden');
      }
    });
  }

  initViewers() {
    this.viewerOriginal = new MedicalViewer(this.canvasOriginal, {
      onStateChange: (st) => this.updateHUDs(st),
      onSliceChange: (delta) => this.navigateSlice(delta),
    });

    this.viewerAi = new MedicalViewer(this.canvasAi, {
      isAiSlot: true,
      onStateChange: (st) => this.updateHUDs(st),
      onSliceChange: (delta) => this.navigateSlice(delta),
    });

    this.curtainOriginalViewer = new MedicalViewer(this.canvasCurtainOriginal, {
      onSliceChange: (delta) => this.navigateSlice(delta),
    });

    this.curtainDenoisedViewer = new MedicalViewer(this.canvasCurtainDenoised, {
      isAiSlot: true,
      onSliceChange: (delta) => this.navigateSlice(delta),
    });

    if (this.state.isSync) {
      this.viewerOriginal.setSyncPartner(this.viewerAi);
      this.viewerAi.setSyncPartner(this.viewerOriginal);
      this.curtainOriginalViewer.setSyncPartner(this.curtainDenoisedViewer);
      this.curtainDenoisedViewer.setSyncPartner(this.curtainOriginalViewer);
    }
  }

  bindEvents() {
    // Search
    this.patientSearchInput.addEventListener('input', (e) => {
      this.filterPatients(e.target.value);
    });

    // Anonymization Toggle
    this.anonymizeToggle.addEventListener('change', (e) => {
      this.state.isAnonymized = e.target.checked;
      this.renderPatientTree();
      this.updateHeaderContext();
      this.updateMetadataPanel();
    });

    // View Modes
    document.querySelectorAll('[data-view-mode]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const mode = e.currentTarget.getAttribute('data-view-mode');
        this.setViewMode(mode);
      });
    });

    // Tools
    document.querySelectorAll('[data-tool]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const tool = e.currentTarget.getAttribute('data-tool');
        this.setActiveTool(tool);
      });
    });

    // Presets
    const presetSelect = document.getElementById('preset-select');
    if (presetSelect) {
      presetSelect.addEventListener('change', (e) => {
        this.viewerOriginal.setPreset(e.target.value);
        if (this.curtainOriginalViewer) {
          this.curtainOriginalViewer.setPreset(e.target.value);
        }
      });
    }

    // Actions
    document.getElementById('btn-invert').addEventListener('click', () => {
      this.viewerOriginal.toggleInvert();
      if (this.curtainOriginalViewer) this.curtainOriginalViewer.toggleInvert();
    });

    document.getElementById('btn-reset').addEventListener('click', () => {
      this.viewerOriginal.resetTransform();
      if (this.curtainOriginalViewer) this.curtainOriginalViewer.resetTransform();
    });

    document.getElementById('btn-fit').addEventListener('click', () => {
      this.viewerOriginal.fitToWindow();
      if (this.curtainOriginalViewer) this.curtainOriginalViewer.fitToWindow();
    });

    document.getElementById('btn-zoom-in').addEventListener('click', () => {
      this.viewerOriginal.setZoomDelta(0.15);
      if (this.curtainOriginalViewer) this.curtainOriginalViewer.setZoomDelta(0.15);
    });

    document.getElementById('btn-zoom-out').addEventListener('click', () => {
      this.viewerOriginal.setZoomDelta(-0.15);
      if (this.curtainOriginalViewer) this.curtainOriginalViewer.setZoomDelta(-0.15);
    });

    document.getElementById('btn-fullscreen').addEventListener('click', () => {
      this.toggleFullscreen();
    });

    // Sync Toggle
    this.btnSync.addEventListener('click', () => {
      this.state.isSync = !this.state.isSync;
      this.btnSync.classList.toggle('active', this.state.isSync);
      if (this.state.isSync) {
        this.viewerOriginal.setSyncPartner(this.viewerAi);
        this.viewerAi.setSyncPartner(this.viewerOriginal);
      } else {
        this.viewerOriginal.setSyncPartner(null);
        this.viewerAi.setSyncPartner(null);
      }
    });

    // Slice Controls
    this.sliceSlider.addEventListener('input', (e) => {
      this.setSliceIndex(parseInt(e.target.value, 10));
    });

    this.btnPrevSlice.addEventListener('click', () => this.navigateSlice(-1));
    this.btnNextSlice.addEventListener('click', () => this.navigateSlice(1));

    this.btnCinePlay.addEventListener('click', () => this.toggleCineLoop());

    // Curtain Slider Handle Drag
    this.initCurtainHandleEvents();

    // Modals events
    this.initModalEvents();

    // Left Patients Panel Toggle
    if (this.btnCollapseSidebarLeft) {
      this.btnCollapseSidebarLeft.addEventListener('click', () => this.togglePatientsPanel(false));
    }
    if (this.btnExpandSidebarLeft) {
      this.btnExpandSidebarLeft.addEventListener('click', () => this.togglePatientsPanel(true));
    }
    if (this.btnTogglePatientsToolbar) {
      this.btnTogglePatientsToolbar.addEventListener('click', () => this.togglePatientsPanel());
    }

    // Metadata Panel Toggle
    if (this.btnCollapseSidebarRight) {
      this.btnCollapseSidebarRight.addEventListener('click', () => this.toggleMetadataPanel(false));
    }
    if (this.btnExpandSidebarRight) {
      this.btnExpandSidebarRight.addEventListener('click', () => this.toggleMetadataPanel(true));
    }
    if (this.btnToggleMetaToolbar) {
      this.btnToggleMetaToolbar.addEventListener('click', () => this.toggleMetadataPanel());
    }

    // Close Exam action
    if (this.btnCloseExam) {
      this.btnCloseExam.addEventListener('click', () => this.closeCurrentExam());
    }
    if (this.btnEmptyUpload) {
      this.btnEmptyUpload.addEventListener('click', () => {
        this.uploadModal.classList.add('open');
      });
    }
  }

  closeCurrentExam() {
    this.state.currentPatient = null;
    this.state.currentStudy = null;
    this.state.currentSeries = null;
    this.state.instances = [];
    this.state.currentSliceIndex = 0;

    // Reset all viewers
    this.viewerOriginal.clear();
    this.viewerAi.clear();
    if (this.curtainOriginalViewer) this.curtainOriginalViewer.clear();
    if (this.curtainDenoisedViewer) this.curtainDenoisedViewer.clear();

    // Update Header Context
    this.headerPatientName.textContent = 'Aucun patient sélectionné';
    this.headerStudyDesc.textContent = '---';
    this.headerSeriesDesc.textContent = '---';

    // Hide Close Exam button
    if (this.btnCloseExam) this.btnCloseExam.style.display = 'none';

    // Update slice UI
    this.sliceDisplay.textContent = 'Coupe 0 / 0';
    this.sliceLocationDisplay.textContent = '';
    this.sliceSlider.min = 0;
    this.sliceSlider.max = 0;
    this.sliceSlider.value = 0;

    // Clear HUDs
    document.querySelectorAll('.viewport-hud').forEach((el) => { el.innerHTML = ''; });

    // Show empty placeholder in viewport
    if (this.viewportEmptyPlaceholder) this.viewportEmptyPlaceholder.style.display = 'flex';

    // Reset active tree selections
    document.querySelectorAll('.patient-tree-item.active, .series-item.active').forEach((el) => {
      el.classList.remove('active');
    });

    // Clear metadata panel
    const metaContainer = document.getElementById('metadata-summary-container');
    if (metaContainer) {
      metaContainer.innerHTML = '<p class="empty-state-text" style="padding: 24px; text-align: center; color: var(--text-muted);">Aucun examen ouvert</p>';
    }
  }

  togglePatientsPanel(show = null) {
    if (!this.sidebarLeft) return;
    const isCurrentlyCollapsed = this.sidebarLeft.classList.contains('collapsed');
    const shouldCollapse = (show !== null) ? !show : !isCurrentlyCollapsed;

    if (shouldCollapse) {
      this.sidebarLeft.classList.add('collapsed');
      if (this.btnExpandSidebarLeft) this.btnExpandSidebarLeft.classList.add('visible');
      if (this.btnTogglePatientsToolbar) this.btnTogglePatientsToolbar.classList.remove('active');
    } else {
      this.sidebarLeft.classList.remove('collapsed');
      if (this.btnExpandSidebarLeft) this.btnExpandSidebarLeft.classList.remove('visible');
      if (this.btnTogglePatientsToolbar) this.btnTogglePatientsToolbar.classList.add('active');
    }

    // Trigger viewer resize so medical viewports adapt smoothly to extra space
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
      if (this.viewerOriginal) this.viewerOriginal.fitToWindow();
      if (this.viewerAi) this.viewerAi.fitToWindow();
      if (this.curtainOriginalViewer) this.curtainOriginalViewer.fitToWindow();
      if (this.curtainDenoisedViewer) this.curtainDenoisedViewer.fitToWindow();
    }, 260);
  }

  toggleMetadataPanel(show = null) {
    if (!this.sidebarRight) return;
    const isCurrentlyCollapsed = this.sidebarRight.classList.contains('collapsed');
    const shouldCollapse = (show !== null) ? !show : !isCurrentlyCollapsed;

    if (shouldCollapse) {
      this.sidebarRight.classList.add('collapsed');
      if (this.btnExpandSidebarRight) this.btnExpandSidebarRight.classList.add('visible');
      if (this.btnToggleMetaToolbar) this.btnToggleMetaToolbar.classList.remove('active');
    } else {
      this.sidebarRight.classList.remove('collapsed');
      if (this.btnExpandSidebarRight) this.btnExpandSidebarRight.classList.remove('visible');
      if (this.btnToggleMetaToolbar) this.btnToggleMetaToolbar.classList.add('active');
    }

    // Trigger viewer resize so medical viewports adapt smoothly to extra space
    setTimeout(() => {
      window.dispatchEvent(new Event('resize'));
      if (this.viewerOriginal) this.viewerOriginal.fitToWindow();
      if (this.viewerAi) this.viewerAi.fitToWindow();
      if (this.curtainOriginalViewer) this.curtainOriginalViewer.fitToWindow();
      if (this.curtainDenoisedViewer) this.curtainDenoisedViewer.fitToWindow();
    }, 260);
  }

  initCurtainHandleEvents() {
    let isCurtainDragging = false;

    const onCurtainMove = (clientX) => {
      if (!this.curtainContainer) return;
      const rect = this.curtainContainer.getBoundingClientRect();
      const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
      const pct = (x / rect.width) * 100;
      this.state.curtainPos = pct;

      this.curtainHandle.style.left = `${pct}%`;
      this.curtainTopLayer.style.clipPath = `polygon(0 0, ${pct}% 0, ${pct}% 100%, 0 100%)`;
    };

    this.curtainHandle.addEventListener('mousedown', (e) => {
      isCurtainDragging = true;
      e.preventDefault();
    });

    window.addEventListener('mousemove', (e) => {
      if (isCurtainDragging) {
        onCurtainMove(e.clientX);
      }
    });

    window.addEventListener('mouseup', () => {
      isCurtainDragging = false;
    });
  }

  initModalEvents() {
    // Upload Modal
    const openUpload = () => {
      this.uploadModal.classList.add('open');
      this.uploadProgress.style.display = 'none';
      this.uploadProgressFill.style.width = '0%';
      this.uploadStatusText.textContent = '';
    };

    if (this.btnOpenUpload) this.btnOpenUpload.addEventListener('click', openUpload);
    if (this.btnOpenUploadSidebar) this.btnOpenUploadSidebar.addEventListener('click', openUpload);
    this.btnCloseUpload.addEventListener('click', () => this.uploadModal.classList.remove('open'));

    // Dropzone inside modal
    this.dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      this.dropzone.classList.add('dragover');
    });

    this.dropzone.addEventListener('dragleave', () => {
      this.dropzone.classList.remove('dragover');
    });

    this.dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      this.dropzone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        this.handleFileUpload(e.dataTransfer.files);
      }
    });

    // Global drag & drop on window
    window.addEventListener('dragover', (e) => {
      e.preventDefault();
    });

    window.addEventListener('drop', (e) => {
      e.preventDefault();
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        this.uploadModal.classList.add('open');
        this.handleFileUpload(e.dataTransfer.files);
      }
    });

    document.getElementById('btn-select-files').addEventListener('click', () => {
      this.fileInput.click();
    });

    document.getElementById('btn-select-folder').addEventListener('click', () => {
      this.folderInput.click();
    });

    this.fileInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) this.handleFileUpload(e.target.files);
    });

    this.folderInput.addEventListener('change', (e) => {
      if (e.target.files.length > 0) this.handleFileUpload(e.target.files);
    });

    // Metadata Modal
    this.btnAllMetadata.addEventListener('click', () => this.openAllMetadataModal());
    this.btnCloseMetadata.addEventListener('click', () => this.metadataModal.classList.remove('open'));

    this.tagSearchInput.addEventListener('input', (e) => {
      this.filterMetadataTags(e.target.value);
    });

    // Shortcuts Modal
    this.btnOpenShortcuts.addEventListener('click', () => this.shortcutsModal.classList.add('open'));
    this.btnCloseShortcuts.addEventListener('click', () => this.shortcutsModal.classList.remove('open'));

    // AI Modal
    this.btnCloseAiInfo.addEventListener('click', () => this.aiInfoModal.classList.remove('open'));
  }

  async handleFileUpload(fileList) {
    this.uploadProgress.style.display = 'block';
    this.uploadProgressFill.style.width = '15%';
    this.uploadStatusText.textContent = `Envoi de ${fileList.length} fichier(s) DICOM...`;

    try {
      const result = await API.uploadFiles(fileList, (pct) => {
        this.uploadProgressFill.style.width = `${pct}%`;
        this.uploadStatusText.textContent = `Téléversement : ${pct}% (Analyse DICOM...)`;
      });

      // Clear file input values immediately so subsequent uploads can be triggered cleanly
      if (this.fileInput) this.fileInput.value = '';
      if (this.folderInput) this.folderInput.value = '';

      this.uploadProgressFill.style.width = '100%';
      this.uploadStatusText.innerHTML = `
        <span style="color: var(--status-success); font-weight: 600;">
          ✓ ${result.message}
        </span>
      `;

      // Automatically close modal after 350ms as clear indication of success (never stays stuck)
      setTimeout(() => {
        this.uploadModal.classList.remove('open');
        this.uploadProgress.style.display = 'none';
        this.uploadStatusText.textContent = '';
      }, 350);

      // Refresh patients and immediately select the uploaded patient
      this.state.patients = await API.getPatients();
      this.renderPatientTree();
      if (this.state.patients.length > 0) {
        // First patient in list is the most recently imported/created
        await this.selectPatient(this.state.patients[0].patient_id);
      }
    } catch (err) {
      if (this.fileInput) this.fileInput.value = '';
      if (this.folderInput) this.folderInput.value = '';
      this.uploadStatusText.innerHTML = `
        <span style="color: var(--status-danger); font-weight: 600;">
          ✗ Erreur d'importation : ${err.message}
        </span>
      `;
    }
  }

  bindKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

      switch (e.key) {
        case 'ArrowUp':
        case 'ArrowLeft':
          e.preventDefault();
          this.navigateSlice(-1);
          break;
        case 'ArrowDown':
        case 'ArrowRight':
          e.preventDefault();
          this.navigateSlice(1);
          break;
        case 'w':
        case 'W':
          this.setActiveTool('wl');
          break;
        case 'p':
        case 'P':
          this.setActiveTool('pan');
          break;
        case 'z':
        case 'Z':
          this.setActiveTool('zoom');
          break;
        case 'r':
        case 'R':
          this.viewerOriginal.resetTransform();
          break;
        case 'i':
        case 'I':
          this.viewerOriginal.toggleInvert();
          break;
        case ' ':
          e.preventDefault();
          this.toggleCineLoop();
          break;
        case 'f':
        case 'F':
          this.toggleFullscreen();
          break;
        case 's':
        case 'S':
          this.setActiveTool('scroll');
          break;
        case 'y':
        case 'Y':
          this.btnSync.click();
          break;
        case 'm':
        case 'M':
          this.toggleMetadataPanel();
          break;
        case 'b':
        case 'B':
          this.togglePatientsPanel();
          break;
      }
    });
  }

  async loadPatients(query = '') {
    try {
      this.state.patients = await API.getPatients(query);
      this.renderPatientTree();

      // Auto-select first patient & series if none selected
      if (!this.state.currentPatient && this.state.patients.length > 0) {
        await this.selectPatient(this.state.patients[0].patient_id);
      }
    } catch (err) {
      console.error('Erreur chargement patients:', err);
    }
  }

  renderPatientTree() {
    if (!this.patientListContainer) return;
    this.patientListContainer.innerHTML = '';

    if (this.state.patients.length === 0) {
      this.patientListContainer.innerHTML = `
        <div class="empty-state">
          <p>Aucun patient trouvé</p>
        </div>
      `;
      return;
    }

    this.state.patients.forEach((patient) => {
      const isSelected = this.state.currentPatient && this.state.currentPatient.patient_id === patient.patient_id;
      const card = document.createElement('div');
      card.className = `patient-card ${isSelected ? 'active' : ''}`;

      const displayName = this.state.isAnonymized
        ? `Patient ${patient.patient_id}`
        : patient.patient_name;

      card.innerHTML = `
        <div class="patient-header">
          <div class="patient-info">
            <div class="patient-name-row">
              <span>${displayName}</span>
              <span class="patient-id-badge">${patient.patient_id}</span>
            </div>
            <div class="patient-meta-row">
              <span class="badge-lumbar">IRM Lombaire</span>
              <span>${patient.patient_sex || 'M'} • ${patient.studies_count || 1} examen(s)</span>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <button class="btn-delete-patient" title="Supprimer ce patient" style="background: none; border: none; color: var(--text-muted); cursor: pointer; padding: 2px 4px; font-size: 12px; border-radius: 3px; opacity: 0.6; transition: opacity 0.2s;" onmouseover="this.style.opacity='1'; this.style.color='#ef4444';" onmouseout="this.style.opacity='0.6'; this.style.color='var(--text-muted)';">🗑️</button>
            <span style="color: var(--text-muted); font-size: 10px;">${isSelected ? '▼' : '▶'}</span>
          </div>
        </div>
        ${isSelected ? `<div class="patient-tree-body" id="tree-body-${patient.patient_id}"></div>` : ''}
      `;

      card.querySelector('.patient-header').addEventListener('click', (e) => {
        if (e.target.closest('.btn-delete-patient')) return;
        if (this.state.currentPatient && this.state.currentPatient.patient_id === patient.patient_id) {
          // Replier / Masquer au clic si déjà ouvert
          this.state.currentPatient = null;
          this.renderPatientTree();
          this.updateHeaderContext();
        } else {
          this.selectPatient(patient.patient_id);
        }
      });

      card.querySelector('.patient-header').addEventListener('dblclick', (e) => {
        if (e.target.closest('.btn-delete-patient')) return;
        this.state.currentPatient = null;
        this.renderPatientTree();
        this.updateHeaderContext();
      });

      const btnDelete = card.querySelector('.btn-delete-patient');
      if (btnDelete) {
        btnDelete.addEventListener('click', async (e) => {
          e.stopPropagation();
          const confirmMsg = `Voulez-vous vraiment supprimer le patient ${displayName} (${patient.patient_id}) et toutes ses séries de test ?`;
          if (confirm(confirmMsg)) {
            try {
              await API.deletePatient(patient.patient_id);
              if (this.state.currentPatient && this.state.currentPatient.patient_id === patient.patient_id) {
                this.closeCurrentExam();
              }
              await this.loadPatients();
            } catch (err) {
              alert(`Erreur de suppression: ${err.message}`);
            }
          }
        });
      }

      this.patientListContainer.appendChild(card);

      if (isSelected && this.state.currentPatient.studies) {
        this.renderStudiesTree(patient.patient_id, this.state.currentPatient.studies);
      }
    });
  }

  async selectPatient(patientId) {
    try {
      this.state.currentPatient = await API.getPatient(patientId);
      this.renderPatientTree();
      this.updateHeaderContext();

      if (this.state.currentPatient.studies && this.state.currentPatient.studies.length > 0) {
        const firstStudy = this.state.currentPatient.studies[0];
        this.state.currentStudy = firstStudy;

        if (firstStudy.series && firstStudy.series.length > 0) {
          await this.selectSeries(firstStudy.series[0].series_instance_uid);
        }
      }
    } catch (err) {
      console.error('Erreur sélection patient:', err);
    }
  }

  renderStudiesTree(patientId, studies) {
    const container = document.getElementById(`tree-body-${patientId}`);
    if (!container) return;

    container.innerHTML = '';
    studies.forEach((study) => {
      const studyDiv = document.createElement('div');
      studyDiv.className = 'study-node';

      const studyDateFormatted = study.study_date
        ? `${study.study_date.slice(6, 8)}/${study.study_date.slice(4, 6)}/${study.study_date.slice(0, 4)}`
        : 'Date inconnue';

      studyDiv.innerHTML = `
        <div class="study-header" style="cursor: pointer; user-select: none;" title="Cliquer pour afficher/masquer les séries">
          <span>📅 ${studyDateFormatted}</span>
          <span>• ${study.study_description || 'IRM Rachis Lombaire'}</span>
          <span class="study-chevron" style="margin-left: auto; font-size: 9px; color: var(--text-muted);">▼</span>
        </div>
        <div class="series-list"></div>
      `;

      container.appendChild(studyDiv);

      const studyHeader = studyDiv.querySelector('.study-header');
      const seriesContainer = studyDiv.querySelector('.series-list');

      if (studyHeader && seriesContainer) {
        studyHeader.addEventListener('click', () => {
          const isCollapsed = seriesContainer.style.display === 'none';
          seriesContainer.style.display = isCollapsed ? 'flex' : 'none';
          const ch = studyHeader.querySelector('.study-chevron');
          if (ch) ch.textContent = isCollapsed ? '▼' : '▶';
        });
      }
      if (study.series && seriesContainer) {
        study.series.forEach((ser) => {
          const isSerActive = this.state.currentSeries && this.state.currentSeries.series_instance_uid === ser.series_instance_uid;
          const serDiv = document.createElement('div');
          serDiv.className = `series-item ${isSerActive ? 'active' : ''}`;

          serDiv.innerHTML = `
            <div class="series-title-row">
              <span class="series-title">${ser.series_description || 'Série IRM'}</span>
              <span class="series-modality-badge">${ser.modality || 'MR'}</span>
            </div>
            <div class="series-meta-row">
              <span>${ser.slice_count || 1} coupe(s)</span>
              <span>• e: ${ser.slice_thickness || 3.0}mm</span>
              <span>• TR:${Math.round(ser.repetition_time || 0)} TE:${Math.round(ser.echo_time || 0)}</span>
            </div>
          `;

          serDiv.addEventListener('click', (e) => {
            e.stopPropagation();
            this.selectSeries(ser.series_instance_uid);
          });

          seriesContainer.appendChild(serDiv);
        });
      }
    });
  }

  async selectSeries(seriesUid) {
    try {
      this.state.currentSeries = await API.getSeriesDetail(seriesUid);
      this.state.instances = this.state.currentSeries.instances || [];
      // Always start on the first slice (Coupe 1 / N)
      this.state.currentSliceIndex = 0;

      if (this.viewportEmptyPlaceholder) this.viewportEmptyPlaceholder.style.display = 'none';
      if (this.btnCloseExam) this.btnCloseExam.style.display = 'inline-flex';

      this.updateHeaderContext();
      this.updateSliceSlider();
      this.renderPatientTree();

      await this.loadCurrentSlice(true);

      [50, 150, 350, 600].forEach((delay) => {
        setTimeout(() => {
          if (this.viewerOriginal) {
            this.viewerOriginal.resizeCanvas();
            this.viewerOriginal.fitToWindow();
          }
          if (this.viewerAi) {
            this.viewerAi.resizeCanvas();
            this.viewerAi.fitToWindow();
          }
        }, delay);
      });

      await this.updateMetadataPanel();
    } catch (err) {
      console.error('Erreur chargement série:', err);
    }
  }

  async loadCurrentSlice(forceResetTransform = false, forceReload = false) {
    if (this.state.instances.length === 0) return;
    const inst = this.state.instances[this.state.currentSliceIndex];
    if (!inst) return;

    // Load original viewer immediately (ultra-fast)
    const promises = [this.viewerOriginal.loadInstance(inst, forceReload, forceResetTransform)];

    // Always load or preload AI slot for current slice so switching to "Débruité" is instantaneous!
    if (this.state.viewMode === 'denoised' || this.state.viewMode === 'compare_split') {
      promises.push(this.viewerAi.loadInstance(inst, forceReload, forceResetTransform));
    } else {
      // Background preload for current slice so toggling to "Débruité" is immediately drawn without any lag!
      this.viewerAi.loadInstance(inst, forceReload, forceResetTransform).catch(() => {});
    }

    // Only load curtain viewers if curtain mode is active
    if (this.state.viewMode === 'curtain') {
      if (this.curtainOriginalViewer) promises.push(this.curtainOriginalViewer.loadInstance(inst, forceReload, forceResetTransform));
      if (this.curtainDenoisedViewer) promises.push(this.curtainDenoisedViewer.loadInstance(inst, forceReload, forceResetTransform));
    }

    await Promise.all(promises);

    // Preload adjacent slices (+1, +2, -1, -2) in the background for ultra-smooth sweeping
    this.preloadAdjacentSlices();
  }

  preloadAdjacentSlices() {
    if (!this.state.instances || this.state.instances.length <= 1) return;
    const curr = this.state.currentSliceIndex;
    const offsets = [1, -1, 2, -2];
    for (const offset of offsets) {
      const idx = curr + offset;
      if (idx >= 0 && idx < this.state.instances.length) {
        const inst = this.state.instances[idx];
        const instId = inst.instance_uid || inst.id;
        const img = new Image();
        img.src = `/api/instances/${encodeURIComponent(instId)}/image`;
      }
    }
  }

  setSliceIndex(index) {
    if (this.state.instances.length === 0) return;
    const clamped = Math.max(0, Math.min(index, this.state.instances.length - 1));
    if (clamped === this.state.currentSliceIndex) return;

    this.state.currentSliceIndex = clamped;
    this.sliceSlider.value = clamped;
    this.updateSliceUI(); // Instantaneous HUD & counter feedback
    this.loadCurrentSlice(false);
  }

  navigateSlice(delta) {
    this.setSliceIndex(this.state.currentSliceIndex + delta);
  }

  updateSliceSlider() {
    const total = this.state.instances.length;
    this.sliceSlider.min = 0;
    this.sliceSlider.max = Math.max(0, total - 1);
    this.sliceSlider.value = this.state.currentSliceIndex;
    this.updateSliceUI();
  }

  updateSliceUI() {
    const total = this.state.instances.length;
    const current = this.state.currentSliceIndex + 1;
    this.sliceDisplay.textContent = `Coupe ${current} / ${total}`;

    const inst = this.state.instances[this.state.currentSliceIndex];
    if (inst && inst.slice_location !== null) {
      this.sliceLocationDisplay.textContent = `Pos: ${inst.slice_location.toFixed(1)} mm`;
    } else {
      this.sliceLocationDisplay.textContent = '';
    }

    this.updateHUDs();
  }

  toggleCineLoop() {
    this.state.isCinePlaying = !this.state.isCinePlaying;
    this.btnCinePlay.classList.toggle('active', this.state.isCinePlaying);
    this.btnCinePlay.textContent = this.state.isCinePlaying ? '⏸ Pause' : '▶ Cine';

    if (this.state.isCinePlaying) {
      this.state.cineTimer = setInterval(() => {
        let next = this.state.currentSliceIndex + 1;
        if (next >= this.state.instances.length) next = 0;
        this.setSliceIndex(next);
      }, 1000 / this.state.cineFps);
    } else {
      clearInterval(this.state.cineTimer);
    }
  }

  async setViewMode(mode, forceReload = false) {
    const isSameMode = (this.state.viewMode === mode);
    this.state.viewMode = mode;
    document.querySelectorAll('[data-view-mode]').forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-view-mode') === mode);
    });

    if (mode === 'original') {
      this.viewportsWrapper.style.display = 'flex';
      this.curtainContainer.style.display = 'none';
      this.viewportPanelOriginal.style.display = 'flex';
      this.viewportPanelAi.style.display = 'none';
    } else if (mode === 'denoised') {
      this.viewportsWrapper.style.display = 'flex';
      this.curtainContainer.style.display = 'none';
      this.viewportPanelOriginal.style.display = 'none';
      this.viewportPanelAi.style.display = 'flex';
    } else if (mode === 'compare_split') {
      this.viewportsWrapper.style.display = 'flex';
      this.curtainContainer.style.display = 'none';
      this.viewportPanelOriginal.style.display = 'flex';
      this.viewportPanelAi.style.display = 'flex';
    } else if (mode === 'curtain') {
      this.viewportsWrapper.style.display = 'none';
      this.curtainContainer.style.display = 'block';
      setTimeout(() => {
        if (this.curtainOriginalViewer) this.curtainOriginalViewer.resizeCanvas();
        if (this.curtainDenoisedViewer) this.curtainDenoisedViewer.resizeCanvas();
      }, 50);
    }

    setTimeout(() => {
      this.viewerOriginal.resizeCanvas();
      this.viewerAi.resizeCanvas();
    }, 50);

    // CRITICAL: Immediately load and render the current slice in the selected mode!
    // If the user re-clicks "Débruité", force fresh reload so it re-runs denoising on current slice immediately!
    await this.loadCurrentSlice(false, isSameMode || forceReload);
  }

  setActiveTool(tool) {
    this.state.activeTool = tool;
    document.querySelectorAll('[data-tool]').forEach((btn) => {
      btn.classList.toggle('active', btn.getAttribute('data-tool') === tool);
    });

    this.viewerOriginal.setTool(tool);
    this.viewerAi.setTool(tool);
    if (this.curtainOriginalViewer) this.curtainOriginalViewer.setTool(tool);
    if (this.curtainDenoisedViewer) this.curtainDenoisedViewer.setTool(tool);
  }

  updateHUDs(viewerState = null) {
    const inst = this.state.instances[this.state.currentSliceIndex] || {};
    const p = this.state.currentPatient || {};
    const s = this.state.currentStudy || {};
    const ser = this.state.currentSeries || {};

    const pName = this.state.isAnonymized ? `Patient ${p.patient_id || ''}` : p.patient_name || '';

    // HUD Top Left (Both)
    document.querySelectorAll('.hud-top-left').forEach((el) => {
      el.innerHTML = `
        <div><strong>${pName}</strong></div>
        <div>ID: ${p.patient_id || ''} | Sexe: ${p.patient_sex || 'M'}</div>
      `;
    });

    // HUD Top Right - Original
    const origTopRight = document.querySelector('#viewport-panel-original .hud-top-right');
    if (origTopRight) {
      origTopRight.innerHTML = `
        <div>${ser.series_description || ''}</div>
        <div>${s.study_description || 'IRM Rachis Lombaire'}</div>
        <div>${ser.manufacturer || 'SIEMENS'} 3.0T (DICOM Brut)</div>
      `;
    }

    // HUD Top Right - AI
    const aiTopRight = document.querySelector('.hud-ai-top-right');
    if (aiTopRight) {
      aiTopRight.innerHTML = `
        <div style="color: var(--accent-hover); font-weight: 600;">✦ ResNet 2D Denoiser</div>
        <div>MLflow: Best Fold 2</div>
        <div style="color: #10b981;">Inférence GPU CUDA Active</div>
      `;
    }

    // HUD Bottom Left - Original
    const origBottomLeft = document.querySelector('#viewport-panel-original .hud-bottom-left');
    if (origBottomLeft) {
      origBottomLeft.innerHTML = `
        <div>TR: ${Math.round(ser.repetition_time || 0)}ms  TE: ${Math.round(ser.echo_time || 0)}ms</div>
        <div>Épaisseur: ${inst.slice_thickness || 3.0}mm</div>
        <div>Matrice: ${inst.rows || 384}x${inst.columns || 384}</div>
      `;
    }

    // HUD Bottom Left - AI
    const aiBottomLeft = document.querySelector('.hud-ai-bottom-left');
    if (aiBottomLeft) {
      aiBottomLeft.innerHTML = `
        <div>Architecture: 8 ResBlocks (64 feat)</div>
        <div>Normalisation: Pair-consistent</div>
        <div>Précision: Float32 Tensor</div>
      `;
    }

    // HUD Bottom Right
    const current = this.state.currentSliceIndex + 1;
    const total = this.state.instances.length;
    const wc = viewerState ? Math.round(viewerState.windowCenter || 300) : Math.round(this.viewerOriginal.windowCenter || 300);
    const ww = viewerState ? Math.round(viewerState.windowWidth || 600) : Math.round(this.viewerOriginal.windowWidth || 600);
    const zoom = viewerState ? Math.round(viewerState.zoom * 100) : Math.round(this.viewerOriginal.zoom * 100);

    document.querySelectorAll('.hud-bottom-right').forEach((el) => {
      el.innerHTML = `
        <div>Coupe: ${current} / ${total}</div>
        <div>W: ${ww}  C: ${wc}</div>
        <div>Zoom: ${zoom}%</div>
      `;
    });
  }

  updateHeaderContext() {
    const p = this.state.currentPatient;
    const s = this.state.currentStudy;
    const ser = this.state.currentSeries;

    if (p) {
      this.headerPatientName.textContent = this.state.isAnonymized
        ? `Patient ${p.patient_id}`
        : `${p.patient_name} (${p.patient_id})`;
    } else {
      this.headerPatientName.textContent = '--';
    }

    this.headerStudyDesc.textContent = s ? s.study_description : '--';
    this.headerSeriesDesc.textContent = ser ? ser.series_description : '--';
    // Export Button Handler
    const btnExportDenoised = document.getElementById('btn-export-denoised');
    if (btnExportDenoised) {
      btnExportDenoised.addEventListener('click', () => {
        if (!this.state.currentSeries) {
          alert('Veuillez d\'abord sélectionner une série IRM.');
          return;
        }
        const exportUrl = API.getExportSeriesDenoisedUrl(this.state.currentSeries.series_instance_uid);
        window.location.href = exportUrl;
      });
    }
  }

  async updateMetadataPanel() {
    if (!this.metadataContent) return;
    if (this.state.instances.length === 0) {
      this.metadataContent.innerHTML = '<div class="empty-state"><p>Aucune donnée active</p></div>';
      return;
    }

    const inst = this.state.instances[this.state.currentSliceIndex];
    const p = this.state.currentPatient || {};
    const s = this.state.currentStudy || {};
    const ser = this.state.currentSeries || {};

    const pName = this.state.isAnonymized ? `Patient ${p.patient_id}` : p.patient_name;

    // Base HTML
    this.metadataContent.innerHTML = `
      <!-- CARTE RESTAURATION IA -->
      <div class="meta-card" style="border-color: rgba(14, 165, 233, 0.4); background: linear-gradient(180deg, rgba(14, 165, 233, 0.08) 0%, rgba(13, 18, 25, 0.95) 100%);">
        <div class="meta-card-title" style="color: var(--accent-hover); display: flex; justify-content: space-between;">
          <span>✦ Restauration IA (ResNet 2D)</span>
          <span style="font-size: 9px; background: rgba(16, 185, 129, 0.2); color: #10b981; padding: 1px 6px; border-radius: 3px;">CUDA GPU</span>
        </div>
        <div class="meta-grid" id="metrics-live-grid">
          <div class="meta-item"><span class="meta-label">Temps Inférence</span><span class="meta-value" id="metric-time">Calcul...</span></div>
          <div class="meta-item"><span class="meta-label">Réduction Bruit</span><span class="meta-value" id="metric-noise" style="color: #10b981;">--</span></div>
          <div class="meta-item"><span class="meta-label">PSNR estimé</span><span class="meta-value" id="metric-psnr">--</span></div>
          <div class="meta-item"><span class="meta-label">SSIM (Structure)</span><span class="meta-value" id="metric-ssim">--</span></div>
          <div class="meta-item full-width"><span class="meta-label">Modèle MLflow</span><span class="meta-value">ResNetDenoiser (Best Fold 2)</span></div>
        </div>
      </div>

      <div class="meta-card">
        <div class="meta-card-title">👤 Patient</div>
        <div class="meta-grid">
          <div class="meta-item"><span class="meta-label">Nom</span><span class="meta-value">${pName}</span></div>
          <div class="meta-item"><span class="meta-label">ID Patient</span><span class="meta-value">${p.patient_id || '--'}</span></div>
          <div class="meta-item"><span class="meta-label">Sexe</span><span class="meta-value">${p.patient_sex || 'M'}</span></div>
          <div class="meta-item"><span class="meta-label">Naissance</span><span class="meta-value">${p.patient_birth_date || '--'}</span></div>
        </div>
      </div>

      <div class="meta-card">
        <div class="meta-card-title">🏥 Examen & Série</div>
        <div class="meta-grid">
          <div class="meta-item full-width"><span class="meta-label">Examen</span><span class="meta-value">${s.study_description || '--'}</span></div>
          <div class="meta-item full-width"><span class="meta-label">Série</span><span class="meta-value">${ser.series_description || '--'}</span></div>
          <div class="meta-item"><span class="meta-label">Modalité</span><span class="meta-value">${ser.modality || 'MR'}</span></div>
          <div class="meta-item"><span class="meta-label">Région</span><span class="meta-value">Rachis Lombaire</span></div>
        </div>
      </div>

      <div class="meta-card">
        <div class="meta-card-title">⚡ Paramètres Physiques IRM</div>
        <div class="meta-grid">
          <div class="meta-item"><span class="meta-label">Champ B0</span><span class="meta-value">${ser.magnetic_field_strength || 3.0} T</span></div>
          <div class="meta-item"><span class="meta-label">Constructeur</span><span class="meta-value">${ser.manufacturer || 'SIEMENS'}</span></div>
          <div class="meta-item"><span class="meta-label">TR (Répétition)</span><span class="meta-value">${Math.round(ser.repetition_time || 0)} ms</span></div>
          <div class="meta-item"><span class="meta-label">TE (Écho)</span><span class="meta-value">${Math.round(ser.echo_time || 0)} ms</span></div>
          <div class="meta-item"><span class="meta-label">Épaisseur</span><span class="meta-value">${inst.slice_thickness || 3.0} mm</span></div>
          <div class="meta-item"><span class="meta-label">Matrice</span><span class="meta-value">${inst.rows || 384} × ${inst.columns || 384}</span></div>
          <div class="meta-item full-width"><span class="meta-label">Espacement Pixels</span><span class="meta-value">${inst.pixel_spacing ? inst.pixel_spacing.join(' × ') + ' mm' : '0.65 × 0.65 mm'}</span></div>
        </div>
      </div>

      <div class="meta-card">
        <div class="meta-card-title">👁 Fenêtrage (W / L)</div>
        <div class="meta-grid">
          <div class="meta-item"><span class="meta-label">Window Center</span><span class="meta-value" id="meta-wc-val">${Math.round(this.viewerOriginal.windowCenter || 300)}</span></div>
          <div class="meta-item"><span class="meta-label">Window Width</span><span class="meta-value" id="meta-ww-val">${Math.round(this.viewerOriginal.windowWidth || 600)}</span></div>
        </div>
      </div>
    `;

    // Fetch and populate live metrics
    if (inst && inst.instance_uid) {
      API.getInstanceMetrics(inst.instance_uid).then((m) => {
        const timeEl = document.getElementById('metric-time');
        const noiseEl = document.getElementById('metric-noise');
        const psnrEl = document.getElementById('metric-psnr');
        const ssimEl = document.getElementById('metric-ssim');

        if (timeEl) timeEl.textContent = `${m.inference_time_ms} ms (${m.device})`;
        if (noiseEl) noiseEl.textContent = `-${m.noise_reduction_pct}%`;
        if (psnrEl) psnrEl.textContent = `${m.psnr_db} dB`;
        if (ssimEl) ssimEl.textContent = `${m.ssim}`;
      }).catch((e) => console.warn('Métriques non disponibles:', e));
    }
  }

  async openAllMetadataModal() {
    if (this.state.instances.length === 0) return;
    const inst = this.state.instances[this.state.currentSliceIndex];
    if (!inst) return;

    this.metadataModal.classList.add('open');
    this.metadataTagsBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px;">Chargement des tags DICOM...</td></tr>';

    try {
      const fullMeta = await API.getInstanceMetadata(inst.instance_uid);
      this.cachedTags = fullMeta.all_tags || [];
      this.renderMetadataTagsTable(this.cachedTags);
    } catch (err) {
      this.metadataTagsBody.innerHTML = `<tr><td colspan="4" style="color: var(--status-danger); text-align: center; padding: 20px;">Erreur: ${err.message}</td></tr>`;
    }
  }

  renderMetadataTagsTable(tags) {
    this.metadataTagsBody.innerHTML = '';
    if (tags.length === 0) {
      this.metadataTagsBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px;">Aucun tag trouvé</td></tr>';
      return;
    }

    tags.forEach((t) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><span style="color: var(--accent); font-weight: 600;">${t.tag}</span></td>
        <td><span style="color: var(--text-muted);">${t.vr}</span></td>
        <td>${t.name}</td>
        <td style="color: #cbd5e1; word-break: break-all;">${t.value}</td>
      `;
      this.metadataTagsBody.appendChild(tr);
    });
  }

  filterMetadataTags(query) {
    if (!this.cachedTags) return;
    const q = query.toLowerCase();
    const filtered = this.cachedTags.filter(
      (t) =>
        t.tag.toLowerCase().includes(q) ||
        t.name.toLowerCase().includes(q) ||
        t.value.toLowerCase().includes(q)
    );
    this.renderMetadataTagsTable(filtered);
  }

  async handleFileUpload(fileList) {
    this.uploadProgress.style.display = 'block';
    this.uploadProgressFill.style.width = '10%';
    this.uploadStatusText.textContent = `Envoi de ${fileList.length} fichier(s)...`;

    try {
      const result = await API.uploadFiles(fileList, (pct) => {
        this.uploadProgressFill.style.width = `${pct}%`;
        this.uploadStatusText.textContent = `Téléversement : ${pct}% (Analyse DICOM...)`;
      });

      this.uploadProgressFill.style.width = '100%';
      this.uploadStatusText.innerHTML = `
        <span style="color: var(--status-success); font-weight: 600;">
          ✓ ${result.message}
        </span>
      `;

      await this.loadPatients();
      setTimeout(() => {
        this.uploadModal.classList.remove('open');
      }, 1800);
    } catch (err) {
      this.uploadStatusText.innerHTML = `
        <span style="color: var(--status-danger); font-weight: 600;">
          ✗ Erreur d'importation : ${err.message}
        </span>
      `;
    }
  }

  async openAiStatusModal() {
    this.aiInfoModal.classList.add('open');
    const statusContainer = document.getElementById('ai-status-detail-container');
    if (!statusContainer) return;

    statusContainer.innerHTML = '<p>Interrogation du service de débruitage...</p>';
    try {
      const status = await API.getDenoiseStatus();
      statusContainer.innerHTML = `
        <div style="background: var(--bg-card); padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--border-subtle); display: flex; flex-direction: column; gap: 8px;">
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <span style="color: var(--text-muted);">Modèle cible :</span>
            <strong style="color: var(--text-primary);">${status.target_model}</strong>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <span style="color: var(--text-muted);">Registre :</span>
            <strong style="color: var(--accent);">${status.registry}</strong>
          </div>
          <div style="display: flex; align-items: center; justify-content: space-between;">
            <span style="color: var(--text-muted);">Statut d'intégration :</span>
            <span class="ai-badge">Non connecté (V1)</span>
          </div>
          <p style="font-size: 11px; color: var(--text-secondary); margin-top: 6px; border-top: 1px solid var(--border-subtle); padding-top: 6px;">
            ${status.status_description}
          </p>
        </div>
      `;
    } catch (err) {
      statusContainer.innerHTML = `<p style="color: var(--status-danger);">Erreur : ${err.message}</p>`;
    }
  }

  toggleFullscreen() {
    const elem = document.querySelector('.center-viewport-container');
    if (!document.fullscreenElement) {
      elem.requestFullscreen().catch((err) => console.error(err));
    } else {
      document.exitFullscreen();
    }
  }
}

// Launch app when DOM is ready
window.addEventListener('DOMContentLoaded', () => {
  window.radiologyApp = new AppController();
});
