let accessToken: string | null = null;

type Listener = () => void;
const unauthorizedListeners: Listener[] = [];

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function clearSession() {
  accessToken = null;
}

export function onUnauthorized(listener: Listener) {
  unauthorizedListeners.push(listener);
}

function onUnauthorizedEmit() {
  for (const listener of unauthorizedListeners) listener();
}

// expose for api-client
export const emitUnauthorized = onUnauthorizedEmit;
