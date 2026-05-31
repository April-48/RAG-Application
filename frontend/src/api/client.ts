/**
 * Shared HTTP helpers for calling the FastAPI middleware.
 *
 * Most requests go through apiRequest() which attaches the JWT and normalizes
 * errors. File uploads use uploadWithProgress() because fetch can't report
 * upload progress (we need XMLHttpRequest for that).
 */

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const TOKEN_KEY = "rag_token";

/** Tiny wrapper around localStorage so we don't scatter the key name everywhere. */
export const tokenStorage = {
  /** Read the saved JWT, or null if there isn't one. */
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  /** Store a JWT after login. */
  set: (token: string): void => localStorage.setItem(TOKEN_KEY, token),
  /** Drop the JWT on logout or 401. */
  clear: (): void => localStorage.removeItem(TOKEN_KEY),
};

/** Thrown when the server returns a non-2xx status with a JSON error body. */
export class ApiError extends Error {
  status: number;

  /** Build an error with the server's message and HTTP status. */
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: BodyInit | null;
  auth?: boolean;
}

/** JSON fetch wrapper that attaches the JWT and normalizes errors. */
export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  try {
    return await apiRequestInner<T>(path, options);
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError("Something went wrong. Please try again in a moment.", 0);
  }
}

async function apiRequestInner<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { auth = true, headers, body, ...rest } = options;
  const finalHeaders: Record<string, string> = {
    ...(headers as Record<string, string> | undefined),
  };

  // For FormData uploads, let the browser set Content-Type (needs the boundary).
  if (body && !(body instanceof FormData) && !finalHeaders["Content-Type"]) {
    finalHeaders["Content-Type"] = "application/json";
  }

  if (auth) {
    const token = tokenStorage.get();
    if (token) finalHeaders["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: finalHeaders,
    body,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    if (response.status === 401 && auth) {
      handleUnauthorized();
    }
    const detail =
      (data && (data.detail || data.message)) || response.statusText;
    throw new ApiError(
      typeof detail === "string" ? detail : "Request failed",
      response.status,
    );
  }

  return data as T;
}

/** If the token is dead, clear it and send the user to login. */
function handleUnauthorized(): void {
  tokenStorage.clear();
  const path = window.location.pathname;
  if (path !== "/login" && path !== "/signup") {
    window.location.assign("/login");
  }
}

/** Upload a file with XMLHttpRequest so we can report progress. */
export function uploadWithProgress<T>(
  path: string,
  formData: FormData,
  onProgress?: (percent: number) => void,
): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}${path}`);

    const token = tokenStorage.get();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

    xhr.upload.onprogress = (event) => {
      if (onProgress && event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      const data = xhr.responseText
        ? JSON.parse(xhr.responseText)
        : null;
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data as T);
      } else {
        if (xhr.status === 401) handleUnauthorized();
        const detail =
          (data && (data.detail || data.message)) || xhr.statusText;
        reject(
          new ApiError(
            typeof detail === "string" ? detail : "Upload failed",
            xhr.status,
          ),
        );
      }
    };

    xhr.onerror = () =>
      reject(
        new ApiError("Something went wrong. Please try again in a moment.", 0),
      );
    xhr.send(formData);
  });
}
