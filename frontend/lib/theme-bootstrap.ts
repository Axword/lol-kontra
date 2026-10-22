// Runs before painting; only the theme preference is read, never the guest profile.
export const themeBootstrap = `try{var t=localStorage.getItem('axword-theme');document.documentElement.dataset.theme=t==='light'||t==='dark'?t:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}catch{document.documentElement.dataset.theme='light'}`
