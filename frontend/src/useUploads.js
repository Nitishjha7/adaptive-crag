import { useCallback, useEffect, useState } from "react";

/**
 * Documents the visitor uploaded, and the corpus id that points at them.
 *
 * The session id lives in localStorage so a refresh keeps the uploads that are
 * still indexed on the server. It is a random string rather than anything
 * identifying: its only job is to keep one visitor's documents out of another's
 * retrieval, and the deployed demo has no accounts.
 *
 * `corpus` is what the chat sends with each question. Empty until something is
 * uploaded, which is what makes the backend fall back to the built-in corpus.
 */

const KEY = "crag.upload.session";

function newSession() {
  return Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
}

function readSession() {
  try {
    const existing = localStorage.getItem(KEY);
    if (existing) return existing;
    const fresh = newSession();
    localStorage.setItem(KEY, fresh);
    return fresh;
  } catch {
    // Private browsing blocks storage. Uploads still work for this tab; they
    // just will not survive a refresh.
    return newSession();
  }
}

export default function useUploads() {
  const [session] = useState(readSession);
  const [files, setFiles] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Uploads live on the container's filesystem, which is ephemeral. After a
  // restart the session id is still in localStorage but the collection is gone,
  // so the list is checked against the server rather than trusted.
  useEffect(() => {
    fetch(`/api/documents?corpus=upload:${session}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.documents?.length) setFiles(d.documents);
      })
      .catch(() => {});
  }, [session]);

  const upload = useCallback(
    async (file) => {
      setBusy(true);
      setError(null);
      try {
        const form = new FormData();
        form.append("session", session);
        form.append("file", file);

        const res = await fetch("/api/upload", { method: "POST", body: form });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || `HTTP ${res.status}`);
        }
        const result = await res.json();
        setFiles((f) => [
          ...f.filter((x) => x.id !== result.filename),
          { id: result.filename, title: result.filename, chunks: result.chunks },
        ]);
        return result;
      } catch (e) {
        setError(e.message);
        throw e;
      } finally {
        setBusy(false);
      }
    },
    [session],
  );

  const clear = useCallback(async () => {
    await fetch(`/api/upload/${session}`, { method: "DELETE" }).catch(() => {});
    setFiles([]);
    setError(null);
  }, [session]);

  return {
    session,
    files,
    busy,
    error,
    upload,
    clear,
    // Only route to the upload collection once it has something in it.
    corpus: files.length ? `upload:${session}` : "",
  };
}
