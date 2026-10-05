// C:\AI_YEREL\GK_STUDIO_V3\static\js\state.js
export const State = {
  status: 'IDLE', // IDLE | GENERATING
  currentId: null,
  nextId: 1,
  conversations: {},
  themeMode: 0, // 0: Dark, 1: Light, 2: Dim
  sidebarOpen: true,
  activeProjectName: null,
  activeProjectPackageContent: null,
  projectConvMap: {},
  projectContextSentFor: {},
  currentImages: [],
  currentFilePackage: null,
  // Web arama durumu sohbet bazlidir; normal sohbetlere karismaz.
  webActive: false,
  webTarget: '',
  webApprovalPending: false,

  saveToStorage() {
    try {
      localStorage.setItem('gk_theme_mode', String(this.themeMode));
      localStorage.setItem('gk_sidebar_open', String(this.sidebarOpen));
    } catch (e) {}
  },

  loadFromStorage() {
    try {
      this.themeMode = parseInt(localStorage.getItem('gk_theme_mode') || '0', 10);
      this.sidebarOpen = localStorage.getItem('gk_sidebar_open') !== 'false';
    } catch (e) {}
  }
};