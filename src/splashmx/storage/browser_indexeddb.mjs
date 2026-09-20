// SMX-025 production browser/local project persistence.
//
// IndexedDB owns the coherent editable-project head. Canonical project bytes are
// opaque at this adapter boundary: canonical.serialization (or its browser binding)
// must validate/migrate them before save and after load, before activation. This
// adapter independently protects its own physical rows with SHA-256 digests and a
// versioned store envelope. Cache/OPFS ownership is deliberately not conflated with
// the project head.

export const STORE_SCHEMA = 'splashmx.browser-local-store/1';
export const STORE_FORMAT_VERSION = 1;
export const COMMIT_STAGES = Object.freeze([
  'prepared',
  'revision_recorded',
  'shards_recorded',
  'candidate_verified',
  'head_advanced',
  'committed',
]);

export class SplashMXStorageError extends Error {
  constructor(code, message, { cause = undefined } = {}) {
    super(message, cause === undefined ? undefined : { cause });
    this.name = 'SplashMXStorageError';
    this.code = code;
    this.cause = cause;
  }
}

export function mapBrowserStorageError(error, operation = 'browser storage operation') {
  if (error instanceof SplashMXStorageError) return error;
  const name = String(error?.name || '');
  let code = 'storage.io_failure';
  if (name === 'QuotaExceededError') code = 'storage.quota_exceeded';
  else if (name === 'NotAllowedError' || name === 'SecurityError') code = 'storage.permission_denied';
  else if (name === 'InvalidStateError' || name === 'NotSupportedError') code = 'storage.unavailable';
  else if (name === 'AbortError' || name === 'TransactionInactiveError') code = 'storage.transaction_aborted';
  else if (name === 'UnknownError') code = 'storage.io_failure';
  return new SplashMXStorageError(code, `${operation} failed`, { cause: error });
}

function bytes(value, label) {
  if (value instanceof Uint8Array) return new Uint8Array(value);
  if (value instanceof ArrayBuffer) return new Uint8Array(value.slice(0));
  if (ArrayBuffer.isView(value)) {
    return new Uint8Array(value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength));
  }
  throw new SplashMXStorageError('storage.invalid_input', `${label} must be binary bytes`);
}

function equalBytes(a, b) {
  if (a.byteLength !== b.byteLength) return false;
  for (let i = 0; i < a.byteLength; i += 1) if (a[i] !== b[i]) return false;
  return true;
}

async function digest(value) {
  const data = bytes(value, 'digest input');
  const result = await globalThis.crypto.subtle.digest('SHA-256', data);
  return `sha256:${Array.from(new Uint8Array(result), b => b.toString(16).padStart(2, '0')).join('')}`;
}

function requestResult(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new DOMException('IndexedDB request failed', 'UnknownError'));
  });
}

function transactionDone(transaction) {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onabort = () => reject(transaction.error || new DOMException('IndexedDB transaction aborted', 'AbortError'));
    transaction.onerror = () => {};
  });
}

function revisionKey(projectId, revisionId) {
  return JSON.stringify([projectId, revisionId]);
}

function shardKey(projectId, revisionId, key) {
  return JSON.stringify([projectId, revisionId, key]);
}

function normalizeSerialized(serialized) {
  if (!serialized || typeof serialized !== 'object') {
    throw new SplashMXStorageError('storage.invalid_input', 'serialized project revision must be an object');
  }
  const projectId = String(serialized.projectId || '');
  const revisionId = String(serialized.revisionId || '');
  if (!projectId || !revisionId) {
    throw new SplashMXStorageError('storage.invalid_input', 'projectId and revisionId are required');
  }
  const rootManifest = bytes(serialized.rootManifest, 'rootManifest');
  const entries = serialized.shards instanceof Map
    ? [...serialized.shards.entries()]
    : Object.entries(serialized.shards || {});
  const shards = new Map();
  for (const [key, value] of entries.sort(([a], [b]) => String(a).localeCompare(String(b)))) {
    const text = String(key);
    if (!text || shards.has(text)) {
      throw new SplashMXStorageError('storage.invalid_input', 'shard keys must be unique non-empty strings');
    }
    shards.set(text, bytes(value, `shard ${text}`));
  }
  return { projectId, revisionId, rootManifest, shards };
}

export class IndexedDBProjectStore {
  constructor({
    dbName = 'splashmx-projects-v1',
    indexedDBImpl = globalThis.indexedDB,
    storageManager = globalThis.navigator?.storage,
  } = {}) {
    this.dbName = dbName;
    this.indexedDB = indexedDBImpl;
    this.storageManager = storageManager;
    this.db = null;
    this.strictDurabilitySupported = null;
    this.lastReportedDurability = null;
  }

  async open() {
    if (!this.indexedDB || typeof this.indexedDB.open !== 'function') {
      throw new SplashMXStorageError('storage.unavailable', 'IndexedDB is unavailable');
    }
    if (this.db) {
      await this._assertFormat();
      return this;
    }
    try {
      const request = this.indexedDB.open(this.dbName, 1);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains('metadata')) db.createObjectStore('metadata');
        if (!db.objectStoreNames.contains('revisions')) db.createObjectStore('revisions');
        if (!db.objectStoreNames.contains('shards')) db.createObjectStore('shards');
        if (!db.objectStoreNames.contains('heads')) db.createObjectStore('heads');
      };
      this.db = await requestResult(request);
      this.db.onversionchange = () => {
        this.db?.close();
        this.db = null;
      };
      await this._initializeFormat();
      return this;
    } catch (error) {
      this.close();
      throw mapBrowserStorageError(error, 'opening browser project store');
    }
  }

  close() {
    this.db?.close();
    this.db = null;
  }

  _transaction(stores, mode) {
    if (!this.db) throw new SplashMXStorageError('storage.unavailable', 'browser project store is not open');
    if (mode !== 'readwrite') return this.db.transaction(stores, mode);
    try {
      const tx = this.db.transaction(stores, mode, { durability: 'strict' });
      this.strictDurabilitySupported = true;
      this.lastReportedDurability = tx.durability ?? 'strict-requested';
      return tx;
    } catch (error) {
      if (!(error instanceof TypeError)) throw error;
      const tx = this.db.transaction(stores, mode);
      this.strictDurabilitySupported = false;
      this.lastReportedDurability = tx.durability ?? 'not-reported';
      return tx;
    }
  }

  async _initializeFormat() {
    const tx = this._transaction(['metadata'], 'readwrite');
    const store = tx.objectStore('metadata');
    const currentSchema = await requestResult(store.get('store_schema'));
    const currentVersion = await requestResult(store.get('store_format_version'));
    if (currentSchema === undefined && currentVersion === undefined) {
      store.put(STORE_SCHEMA, 'store_schema');
      store.put(STORE_FORMAT_VERSION, 'store_format_version');
    } else if (currentSchema !== STORE_SCHEMA || currentVersion !== STORE_FORMAT_VERSION) {
      tx.abort();
      throw new SplashMXStorageError('storage.unsupported_store_version', 'browser local-store format is unsupported');
    }
    await transactionDone(tx);
  }

  async _assertFormat() {
    const tx = this._transaction(['metadata'], 'readonly');
    const store = tx.objectStore('metadata');
    const schema = await requestResult(store.get('store_schema'));
    const version = await requestResult(store.get('store_format_version'));
    await transactionDone(tx);
    if (schema !== STORE_SCHEMA) {
      throw new SplashMXStorageError('storage.unsupported_store_format', 'browser local-store schema is unsupported');
    }
    if (version !== STORE_FORMAT_VERSION) {
      throw new SplashMXStorageError('storage.unsupported_store_version', `browser local-store version ${version} is unsupported`);
    }
  }

  static _interrupt(tx, faultAt, stage) {
    if (faultAt !== stage) return;
    if (stage !== 'committed') {
      try { tx.abort(); } catch {}
    }
    throw new SplashMXStorageError('storage.interrupted', `simulated interruption at ${stage}`);
  }

  async saveSerialized(serialized, { faultAt = null } = {}) {
    const prepared = normalizeSerialized(serialized);
    if (faultAt !== null && !COMMIT_STAGES.includes(faultAt)) {
      throw new SplashMXStorageError('storage.invalid_input', `unknown fault stage ${faultAt}`);
    }
    await this.open();
    await this._assertFormat();
    IndexedDBProjectStore._interrupt(null, faultAt, 'prepared');

    const rootDigest = await digest(prepared.rootManifest);
    const shardDigests = new Map();
    for (const [key, payload] of prepared.shards) shardDigests.set(key, await digest(payload));

    let tx;
    try {
      tx = this._transaction(['revisions', 'shards', 'heads'], 'readwrite');
      const revisions = tx.objectStore('revisions');
      const shardStore = tx.objectStore('shards');
      const heads = tx.objectStore('heads');
      const rkey = revisionKey(prepared.projectId, prepared.revisionId);
      const existing = await requestResult(revisions.get(rkey));

      if (existing !== undefined) {
        const oldRoot = bytes(existing.rootManifest, 'stored rootManifest');
        if (existing.rootDigest !== rootDigest || !equalBytes(oldRoot, prepared.rootManifest)) {
          tx.abort();
          throw new SplashMXStorageError('storage.revision_conflict', 'ProjectRevisionId already names different root bytes');
        }
        const oldKeys = Array.isArray(existing.shardKeys) ? [...existing.shardKeys] : [];
        const newKeys = [...prepared.shards.keys()];
        if (JSON.stringify(oldKeys) !== JSON.stringify(newKeys)) {
          tx.abort();
          throw new SplashMXStorageError('storage.revision_conflict', 'ProjectRevisionId already names a different shard set');
        }
        for (const key of newKeys) {
          const old = await requestResult(shardStore.get(shardKey(prepared.projectId, prepared.revisionId, key)));
          if (!old || old.digest !== shardDigests.get(key) || !equalBytes(bytes(old.payload, 'stored shard'), prepared.shards.get(key))) {
            tx.abort();
            throw new SplashMXStorageError('storage.revision_conflict', 'ProjectRevisionId already names different shard bytes');
          }
        }
      } else {
        revisions.put({
          projectId: prepared.projectId,
          revisionId: prepared.revisionId,
          rootManifest: prepared.rootManifest,
          rootDigest,
          shardKeys: [...prepared.shards.keys()],
        }, rkey);
      }
      IndexedDBProjectStore._interrupt(tx, faultAt, 'revision_recorded');

      if (existing === undefined) {
        for (const [key, payload] of prepared.shards) {
          shardStore.put({
            projectId: prepared.projectId,
            revisionId: prepared.revisionId,
            shardKey: key,
            payload,
            digest: shardDigests.get(key),
          }, shardKey(prepared.projectId, prepared.revisionId, key));
        }
      }
      IndexedDBProjectStore._interrupt(tx, faultAt, 'shards_recorded');

      // Queue readback inside the same transaction. Digest checks here catch adapter
      // corruption before the head can advance; canonical/schema checks remain above
      // this adapter and are mandatory before activation.
      const verifyRevision = await requestResult(revisions.get(rkey));
      if (!verifyRevision || verifyRevision.rootDigest !== rootDigest || !equalBytes(bytes(verifyRevision.rootManifest, 'verified root'), prepared.rootManifest)) {
        tx.abort();
        throw new SplashMXStorageError('storage.corrupt_store', 'revision readback failed before publication');
      }
      for (const [key, payload] of prepared.shards) {
        const row = await requestResult(shardStore.get(shardKey(prepared.projectId, prepared.revisionId, key)));
        if (!row || row.digest !== shardDigests.get(key) || !equalBytes(bytes(row.payload, 'verified shard'), payload)) {
          tx.abort();
          throw new SplashMXStorageError('storage.corrupt_store', 'shard readback failed before publication');
        }
      }
      IndexedDBProjectStore._interrupt(tx, faultAt, 'candidate_verified');

      heads.put(prepared.revisionId, prepared.projectId);
      IndexedDBProjectStore._interrupt(tx, faultAt, 'head_advanced');
      await transactionDone(tx);
      IndexedDBProjectStore._interrupt(tx, faultAt, 'committed');
      return {
        projectId: prepared.projectId,
        revisionId: prepared.revisionId,
        requestedDurability: 'strict',
        strictDurabilitySupported: this.strictDurabilitySupported,
        reportedDurability: this.lastReportedDurability,
      };
    } catch (error) {
      if (error instanceof SplashMXStorageError) throw error;
      throw mapBrowserStorageError(error, 'publishing browser project revision');
    }
  }

  async loadSerialized(projectId) {
    await this.open();
    await this._assertFormat();
    const project = String(projectId || '');
    if (!project) throw new SplashMXStorageError('storage.invalid_input', 'projectId is required');
    try {
      const tx = this._transaction(['revisions', 'shards', 'heads'], 'readonly');
      const revisionId = await requestResult(tx.objectStore('heads').get(project));
      if (revisionId === undefined) {
        await transactionDone(tx);
        throw new SplashMXStorageError('storage.not_found', `no local project head for ${project}`);
      }
      const rkey = revisionKey(project, String(revisionId));
      const row = await requestResult(tx.objectStore('revisions').get(rkey));
      if (!row) {
        try { tx.abort(); } catch {}
        throw new SplashMXStorageError('storage.corrupt_store', 'project head references a missing revision');
      }
      const rootManifest = bytes(row.rootManifest, 'stored rootManifest');
      if (row.rootDigest !== await digest(rootManifest)) {
        try { tx.abort(); } catch {}
        throw new SplashMXStorageError('storage.corrupt_store', 'stored root-manifest digest mismatch');
      }
      const keys = Array.isArray(row.shardKeys) ? row.shardKeys : null;
      if (!keys || new Set(keys).size !== keys.length) {
        try { tx.abort(); } catch {}
        throw new SplashMXStorageError('storage.corrupt_store', 'stored revision shard index is malformed');
      }
      const shards = new Map();
      for (const key of keys) {
        const shard = await requestResult(tx.objectStore('shards').get(shardKey(project, String(revisionId), key)));
        if (!shard) {
          try { tx.abort(); } catch {}
          throw new SplashMXStorageError('storage.corrupt_store', `stored shard ${key} is missing`);
        }
        const payload = bytes(shard.payload, `stored shard ${key}`);
        if (shard.digest !== await digest(payload)) {
          try { tx.abort(); } catch {}
          throw new SplashMXStorageError('storage.corrupt_store', `stored shard ${key} failed digest verification`);
        }
        shards.set(String(key), payload);
      }
      await transactionDone(tx);
      return { projectId: project, revisionId: String(revisionId), rootManifest, shards };
    } catch (error) {
      if (error instanceof SplashMXStorageError) throw error;
      throw mapBrowserStorageError(error, 'loading browser project revision');
    }
  }

  async storageStatus({ requestPersistence = false } = {}) {
    if (!this.storageManager) {
      return { supported: false, persisted: null, persistenceRequested: false, persistenceGranted: null, estimate: null };
    }
    try {
      const persisted = typeof this.storageManager.persisted === 'function'
        ? await this.storageManager.persisted()
        : null;
      let persistenceGranted = null;
      if (requestPersistence && typeof this.storageManager.persist === 'function') {
        persistenceGranted = await this.storageManager.persist();
      }
      const estimate = typeof this.storageManager.estimate === 'function'
        ? await this.storageManager.estimate()
        : null;
      return {
        supported: true,
        persisted,
        persistenceRequested: Boolean(requestPersistence),
        persistenceGranted,
        estimate,
      };
    } catch (error) {
      throw mapBrowserStorageError(error, 'querying browser storage status');
    }
  }
}
