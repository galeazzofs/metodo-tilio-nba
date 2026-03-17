// auth.js — Firebase Auth helpers
// Depende de: firebase-config.js carregado antes deste script

firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();

// Persistência de sessão: token limpo ao fechar o navegador
auth.setPersistence(firebase.auth.Auth.Persistence.SESSION).catch(console.error);

/** Entra com email + senha. Lança exceção em caso de falha. */
async function signIn(email, password) {
  await auth.signInWithEmailAndPassword(email, password);
}

/** Cria conta. Lança exceção em caso de falha. */
async function signUp(email, password) {
  await auth.createUserWithEmailAndPassword(email, password);
}

/** Sai da conta. */
async function signOut() {
  await auth.signOut();
}

/** Entra com Google. Tenta popup; cai para redirect se popup bloqueado. */
async function signInWithGoogle() {
  const provider = new firebase.auth.GoogleAuthProvider();
  try {
    await auth.signInWithPopup(provider);
  } catch (e) {
    if (e.code === 'auth/popup-blocked' || e.code === 'auth/cancelled-popup-request') {
      // Popup foi bloqueado pelo navegador — usa redirect como fallback
      await auth.signInWithRedirect(provider);
    } else {
      throw e;
    }
  }
}

// Captura resultado de redirecionamento Google (fallback de popup bloqueado)
auth.getRedirectResult().catch(e => {
  if (e.code) window._googleRedirectError = e;
});

/** Retorna um ID token atualizado para uso nas chamadas de API. Null se não autenticado. */
async function getToken() {
  const user = auth.currentUser;
  if (!user) return null;
  return user.getIdToken(false);
}

/**
 * fetch autenticado — adiciona automaticamente o header Authorization.
 * Uso: await authFetch('/api/bets', { method: 'GET' })
 */
async function authFetch(url, options = {}) {
  const token = await getToken();
  const headers = {
    ...(options.headers || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
  return fetch(url, { ...options, headers });
}

/**
 * Registra callback chamado ao mudar estado de autenticação.
 * Recebe o objeto Firebase user (ou null se deslogado).
 */
function onAuthChange(callback) {
  auth.onAuthStateChanged(callback);
}
