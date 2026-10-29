"use client";

import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileText,
  FolderOpen,
  LoaderCircle,
  LockKeyhole,
  LogOut,
  ListPlus,
  RefreshCw,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type SessionState = "checking" | "anonymous" | "admin";

type ConflictType = "duplicate_content" | "same_name";

type ProductOption = {
  id: string;
  display_name: string;
  category: string;
  aliases: string[];
};

type ImportItem = {
  item_id: string;
  filename: string;
  sha256: string;
  product_ids: string[];
  version_label: string | null;
  confidence: string;
  conflict_type: ConflictType | null;
  conflict_version_label: string | null;
  detected_product_name: string | null;
  status: string;
};

type ImportBatch = {
  batch_id: string;
  items: ImportItem[];
};

type ImportAccepted = {
  batch_id: string | null;
  accepted: number;
  rejected: { filename: string; reason: string }[];
};

type ImportBatchSummary = {
  batch_id: string;
  source_type: string;
  status: string;
  created_by: string;
  item_count: number;
};

type VersionIndex = {
  index_version_id: string;
  status: string;
  chunk_count: number;
  error_message: string | null;
};

type DocumentVersion = {
  id: string;
  document_id: string;
  version_label: string | null;
  status: string;
  requires_manual_approval: boolean;
  approved_at: string | null;
  approved_by: string | null;
  document_name: string | null;
  indexes: VersionIndex[];
};

const confidenceLabels: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};

const statusLabels: Record<string, string> = {
  uploaded: "待解析",
  pending: "待处理",
  prepared: "已准备",
  queued: "正在排队",
  processing: "正在解析",
  indexed: "已索引",
  completed: "已完成",
  cancelled: "已取消",
  failed: "失败",
};

const conflictLabels: Record<string, string> = {
  duplicate_content: "重复文件",
  same_name: "同名不同内容",
};

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "请求失败";
}

async function responseError(response: Response) {
  const body = (await response.json().catch(() => null)) as {
    detail?: string;
  } | null;
  return body?.detail ?? `HTTP ${response.status}`;
}

export default function AdminPage() {
  const [session, setSession] = useState<SessionState>("checking");
  const [password, setPassword] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [batch, setBatch] = useState<ImportBatch | null>(null);
  const [batches, setBatches] = useState<ImportBatchSummary[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [conflictItem, setConflictItem] = useState<ImportItem | null>(null);
  const [conflictVersion, setConflictVersion] = useState("");
  const [productItem, setProductItem] = useState<ImportItem | null>(null);
  const [productInput, setProductInput] = useState("");
  const [versionProductId, setVersionProductId] = useState("");
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [versionsBusy, setVersionsBusy] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const directoryInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch("/api/admin/session", { credentials: "include" })
      .then((response) => {
        setSession(response.ok ? "admin" : "anonymous");
        if (response.ok) void loadBatches();
      })
      .catch(() => setSession("anonymous"));
  }, []);

  useEffect(() => {
    if (session === "admin") void loadProducts();
  }, [session]);

  useEffect(() => {
    if (versionProductId || products.length === 0) return;
    setVersionProductId(products[0].id);
  }, [products, versionProductId]);

  useEffect(() => {
    if (session === "admin" && versionProductId) {
      void loadVersions(versionProductId);
    }
  }, [session, versionProductId]);

  useEffect(() => {
    directoryInputRef.current?.setAttribute("webkitdirectory", "");
    directoryInputRef.current?.setAttribute("directory", "");
  }, [session]);

  const queueItems = useMemo(
    () =>
      batch?.items.filter(
        (item) => item.status === "queued" || item.status === "processing",
      ) ?? [],
    [batch],
  );
  const fileItems = useMemo(
    () =>
      batch?.items.filter(
        (item) =>
          !["queued", "processing", "completed", "cancelled"].includes(
            item.status,
          ),
      ) ?? [],
    [batch],
  );
  const conflicts = useMemo(
    () => fileItems.filter((item) => item.conflict_type),
    [fileItems],
  );
  const pendingVersions = useMemo(
    () =>
      versions.filter(
        (version) =>
          version.requires_manual_approval && !version.approved_at,
      ),
    [versions],
  );
  const approvedVersions = useMemo(
    () =>
      versions.filter(
        (version) =>
          !version.requires_manual_approval || Boolean(version.approved_at),
      ),
    [versions],
  );

  useEffect(() => {
    if (!batch || queueItems.length === 0) return;
    const timer = window.setInterval(() => {
      void loadBatch(batch.batch_id).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [batch, queueItems.length]);

  function acceptFiles(files: FileList | null, label: string) {
    const pdfFiles = Array.from(files ?? []).filter((file) =>
      file.name.toLowerCase().endsWith(".pdf"),
    );
    setSelectedFiles(pdfFiles);
    setError(
      files?.length && !pdfFiles.length ? "所选位置中没有 PDF 文件" : "",
    );
    setMessage(
      pdfFiles.length
        ? `${label}已选择 ${pdfFiles.length} 个 PDF`
        : "",
    );
  }

  async function login(event: FormEvent) {
    event.preventDefault();
    if (!password || busy) return;
    setBusy("login");
    setError("");
    try {
      const response = await fetch("/api/admin/login", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      setPassword("");
      setSession("admin");
    } catch (loginError) {
      setError(errorMessage(loginError));
    } finally {
      setBusy(null);
    }
  }

  async function logout() {
    await fetch("/api/admin/logout", {
      method: "POST",
      credentials: "include",
    });
    setSession("anonymous");
    setBatch(null);
    setSelectedFiles([]);
  }

  async function loadBatch(batchId: string) {
    const response = await fetch(`/api/admin/imports/${batchId}`, {
      credentials: "include",
    });
    if (!response.ok) throw new Error(await responseError(response));
    setBatch((await response.json()) as ImportBatch);
  }

  async function loadBatches() {
    const response = await fetch("/api/admin/imports", {
      credentials: "include",
    });
    if (!response.ok) return;
    setBatches((await response.json()) as ImportBatchSummary[]);
  }

  async function loadVersions(productId: string) {
    if (!productId) {
      setVersions([]);
      return;
    }
    setVersionsBusy(true);
    try {
      const response = await fetch(
        `/api/admin/products/${productId}/versions`,
        { credentials: "include" },
      );
      if (!response.ok) throw new Error(await responseError(response));
      setVersions((await response.json()) as DocumentVersion[]);
    } catch (versionError) {
      setError(errorMessage(versionError));
    } finally {
      setVersionsBusy(false);
    }
  }

  function publishableIndex(version: DocumentVersion) {
    return version.indexes
      .filter((index) => index.status === "completed")
      .sort((left, right) =>
        left.index_version_id.localeCompare(right.index_version_id),
      )
      .at(-1);
  }

  async function approveVersion(version: DocumentVersion) {
    if (versionsBusy) return;
    setVersionsBusy(true);
    setError("");
    try {
      const response = await fetch(
        `/api/admin/versions/${version.id}/approve`,
        {
          method: "POST",
          credentials: "include",
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      setMessage("版本已审批通过");
      await loadVersions(versionProductId);
    } catch (approvalError) {
      setError(errorMessage(approvalError));
    } finally {
      setVersionsBusy(false);
    }
  }

  async function publishVersion(
    version: DocumentVersion,
    index: VersionIndex,
  ) {
    if (versionsBusy) return;
    setVersionsBusy(true);
    setError("");
    try {
      const response = await fetch(
        `/api/admin/versions/${version.id}/publish`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            product_id: versionProductId,
            index_version_id: index.index_version_id,
          }),
        },
      );
      if (!response.ok) throw new Error(await responseError(response));
      setMessage(
        `已发布 ${index.index_version_id}，共 ${index.chunk_count} 个 Chunk`,
      );
      await loadVersions(versionProductId);
    } catch (publishError) {
      setError(errorMessage(publishError));
    } finally {
      setVersionsBusy(false);
    }
  }

  async function uploadSelected(event: FormEvent) {
    event.preventDefault();
    if (!selectedFiles.length || busy) return;
    setBusy("upload");
    setError("");
    setMessage("");
    const formData = new FormData();
    for (const file of selectedFiles) {
      formData.append("files", file, file.name);
      const relativePath =
        (file as File & { webkitRelativePath?: string })
          .webkitRelativePath || file.name;
      formData.append("relative_paths", relativePath);
    }
    try {
      const response = await fetch("/api/admin/imports", {
        method: "POST",
        credentials: "include",
        body: formData,
      });
      if (!response.ok) throw new Error(await responseError(response));
      const accepted = (await response.json()) as ImportAccepted;
      if (accepted.batch_id) {
        await loadBatch(accepted.batch_id);
      }
      await loadBatches();
      setSelectedFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (directoryInputRef.current) directoryInputRef.current.value = "";
      const rejectedText = accepted.rejected.length
        ? `，拒绝 ${accepted.rejected.length} 个：${accepted.rejected
            .map((item) => `${item.filename}（${item.reason}）`)
            .join("；")}`
        : "";
      setMessage(`已接收 ${accepted.accepted} 个文件${rejectedText}`);
    } catch (uploadError) {
      setError(errorMessage(uploadError));
    } finally {
      setBusy(null);
    }
  }

  function normalizedProductName(value: string) {
    return value.trim().toLocaleLowerCase().replace(/\s+/g, "");
  }

  function productLabel(productId: string) {
    return (
      products.find((product) => product.id === productId)?.display_name ??
      productId
    );
  }

  function matchProduct(value: string) {
    const normalized = normalizedProductName(value);
    return products.find((candidate) =>
      [
        candidate.id,
        candidate.display_name,
        ...candidate.aliases,
      ].some(
        (alias) => normalizedProductName(alias) === normalized,
      ),
    );
  }

  function validNewVersion(item: ImportItem, value: string): string | null {
    const current = item.version_label?.trim() ?? "";
    const previous = item.conflict_version_label?.trim() ?? "";
    const version = value.trim();
    if (
      !version ||
      (previous &&
        version.toLocaleLowerCase() === previous.toLocaleLowerCase())
    ) {
      setError("新版本号不能为空，且不能与旧版本相同");
      return null;
    }
    if (
      !previous &&
      current &&
      version.toLocaleLowerCase() === current.toLocaleLowerCase()
    ) {
      return version;
    }
    return version;
  }

  async function updateMetadata(
    item: ImportItem,
    productId: string,
    versionLabel: string | null,
  ) {
    if (!batch) return;
    const response = await fetch(
      `/api/admin/imports/${batch.batch_id}/items/${item.item_id}/metadata`,
      {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_ids: [productId],
          version_label: versionLabel,
        }),
      },
    );
    if (!response.ok) throw new Error(await responseError(response));
    setBatch((await response.json()) as ImportBatch);
  }

  async function updateMetadataByName(
    item: ImportItem,
    productName: string,
    versionLabel: string | null,
  ): Promise<ImportBatch> {
    if (!batch) throw new Error("导入批次不存在");
    const response = await fetch(
      `/api/admin/imports/${batch.batch_id}/items/${item.item_id}/metadata`,
      {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_name: productName,
          version_label: versionLabel,
        }),
      },
    );
    if (!response.ok) throw new Error(await responseError(response));
    const updated = (await response.json()) as ImportBatch;
    setBatch(updated);
    return updated;
  }

  async function resolveConflict(
    item: ImportItem,
    action: "replace_as_new_version" | "cancel",
  ) {
    if (!batch) return;
    const response = await fetch(
      `/api/admin/imports/${batch.batch_id}/conflicts/${item.item_id}/resolve`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      },
    );
    if (!response.ok) throw new Error(await responseError(response));
    setBatch((await response.json()) as ImportBatch);
  }

  async function prepareItem(item: ImportItem) {
    if (!batch) return;
    const response = await fetch(
      `/api/admin/imports/${batch.batch_id}/items/${item.item_id}/prepare`,
      {
        method: "POST",
        credentials: "include",
      },
    );
    if (!response.ok) throw new Error(await responseError(response));
    setBatch((await response.json()) as ImportBatch);
  }

  async function queueWithProduct(item: ImportItem, productId: string) {
    if (!batch || busy) return;
    setError("");
    setBusy(item.item_id);
    try {
      if (
        item.product_ids.length !== 1 ||
        item.product_ids[0] !== productId
      ) {
        await updateMetadata(item, productId, item.version_label);
      }
      if (item.conflict_type === "same_name") {
        setConflictItem({ ...item, product_ids: [productId] });
        setConflictVersion(item.version_label ?? "");
        setMessage("请选择覆盖或取消上传");
        return;
      }
      if (item.conflict_type === "duplicate_content") {
        setError("重复文件不能覆盖，请取消上传");
        return;
      }
      await prepareItem(item);
      setMessage("已加入索引队列");
      await loadBatches();
    } catch (queueError) {
      setError(errorMessage(queueError));
    } finally {
      setBusy(null);
    }
  }

  function requestQueue(item: ImportItem) {
    if (busy) return;
    if (item.product_ids.length === 1) {
      void queueWithProduct(item, item.product_ids[0]);
      return;
    }
    setError("");
    setProductInput(item.detected_product_name ?? "");
    setProductItem(item);
  }

  async function loadProducts() {
    try {
      const response = await fetch("/api/products");
      if (!response.ok) throw new Error(await responseError(response));
      setProducts((await response.json()) as ProductOption[]);
    } catch {
      setProducts([]);
    }
  }

  async function queueWithProductName(
    item: ImportItem,
    productName: string,
  ) {
    if (busy) return;
    setBusy(item.item_id);
    setError("");
    try {
      const updatedBatch = await updateMetadataByName(
        item,
        productName,
        item.version_label,
      );
      const updated =
        updatedBatch.items.find(
          (candidate) => candidate.item_id === item.item_id,
        ) ?? item;
      await loadProducts();
      if (updated.product_ids.length === 1) {
        setVersionProductId(updated.product_ids[0]);
      }
      if (updated.conflict_type === "same_name") {
        setConflictItem(updated);
        setConflictVersion(updated.version_label ?? "");
        setMessage("请选择覆盖或取消上传");
        return;
      }
      await prepareItem(updated);
      setMessage("已创建产品并加入索引队列");
      await loadBatches();
    } catch (queueError) {
      setError(errorMessage(queueError));
    } finally {
      setBusy(null);
    }
  }

  function confirmProduct() {
    if (!productItem) return;
    const product = matchProduct(productInput);
    const productName = productInput.trim();
    if (!productName) {
      setError("产品名称不能为空");
      return;
    }
    const item = productItem;
    setProductItem(null);
    if (product) {
      void queueWithProduct(item, product.id);
    } else {
      void queueWithProductName(item, productName);
    }
  }

  async function overwriteItem() {
    if (!conflictItem || busy) return;
    const version = validNewVersion(conflictItem, conflictVersion);
    if (!version) return;
    const productId = conflictItem.product_ids[0];
    setBusy(conflictItem.item_id);
    setError("");
    try {
      await updateMetadata(conflictItem, productId, version);
      await resolveConflict(conflictItem, "replace_as_new_version");
      await prepareItem(conflictItem);
      setConflictItem(null);
      setConflictVersion("");
      setMessage("旧版本已标记替换，新文件已加入解析队列");
      await loadBatches();
    } catch (overwriteError) {
      setError(errorMessage(overwriteError));
    } finally {
      setBusy(null);
    }
  }

  async function cancelItem(item: ImportItem) {
    if (!batch || busy) return;
    setBusy(item.item_id);
    setError("");
    try {
      await resolveConflict(item, "cancel");
      setConflictItem(null);
      setConflictVersion("");
      setMessage("已取消上传");
      await loadBatches();
    } catch (cancelError) {
      setError(errorMessage(cancelError));
    } finally {
      setBusy(null);
    }
  }

  async function refresh() {
    if (!batch || busy) return;
    setBusy("refresh");
    setError("");
    try {
      await loadBatch(batch.batch_id);
      setMessage("状态已刷新");
    } catch (refreshError) {
      setError(errorMessage(refreshError));
    } finally {
      setBusy(null);
    }
  }

  function renderVersionGroup(
    kind: "pending" | "approved",
    items: DocumentVersion[],
  ) {
    const pending = kind === "pending";
    return (
      <div className={`admin-version-group ${kind}`}>
        <div className="admin-list-heading">
          <strong>{pending ? "待审批" : "已审批"}</strong>
          <span>{items.length} 个版本</span>
        </div>
        {items.length ? (
          <div className="admin-table-wrap">
            <table className="admin-table admin-version-table">
              <thead>
                <tr>
                  <th>文件名称</th>
                  <th>版本</th>
                  <th>状态</th>
                  <th>审批</th>
                  <th>索引</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {items.map((version) => {
                  const index = publishableIndex(version);
                  return (
                    <tr key={version.id}>
                      <td>
                        <div className="admin-file-cell">
                          <FileText size={16} />
                          <span>{version.document_name ?? "未知文件"}</span>
                        </div>
                      </td>
                      <td>
                        <strong>
                          {version.version_label ?? version.id.slice(0, 10)}
                        </strong>
                        <code>{version.id.slice(0, 12)}</code>
                      </td>
                      <td>
                        <span
                          className={`admin-tag version-${version.status}`}
                        >
                          {version.status}
                        </span>
                      </td>
                      <td>
                        {pending
                          ? "待人工审批"
                          : version.requires_manual_approval
                            ? `已审批 · ${version.approved_by ?? "admin"}`
                            : "无需审批"}
                      </td>
                      <td>
                        <div className="admin-index-list">
                          {version.indexes.length ? (
                            version.indexes.map((item) => (
                              <span
                                className={`admin-tag index-${item.status}`}
                                key={item.index_version_id}
                              >
                                {item.index_version_id} · {item.status} ·{" "}
                                {item.chunk_count} Chunk
                              </span>
                            ))
                          ) : (
                            <span className="admin-tag">未索引</span>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="admin-row-actions">
                          {pending && (
                            <button
                              type="button"
                              onClick={() => void approveVersion(version)}
                              disabled={versionsBusy}
                            >
                              <CheckCircle2 size={14} />
                              审批通过
                            </button>
                          )}
                          {!pending &&
                            index &&
                            version.status !== "active" && (
                              <button
                                type="button"
                                onClick={() =>
                                  void publishVersion(version, index)
                                }
                                disabled={versionsBusy}
                              >
                                <Upload size={14} />
                                发布
                              </button>
                            )}
                          {!pending && version.status === "active" && (
                            <span className="admin-tag status-indexed">
                              当前活动
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="admin-empty compact">
            <span>
              {versionsBusy
                ? "正在加载版本…"
                : pending
                  ? "暂无待审批版本"
                  : "暂无已审批版本"}
            </span>
          </div>
        )}
      </div>
    );
  }

  if (session === "checking") {
    return (
      <main className="admin-login-shell">
        <LoaderCircle className="spin" size={24} />
      </main>
    );
  }

  if (session === "anonymous") {
    return (
      <main className="admin-login-shell">
        <section className="admin-login-panel">
          <div className="admin-login-brand">
            <LockKeyhole size={22} />
            文档管理
          </div>
          <form onSubmit={login}>
            <label className="admin-field-label" htmlFor="admin-password">
              管理员密码
            </label>
            <input
              className="admin-text-input"
              id="admin-password"
              name="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoFocus
            />
            <button
              className="admin-primary-button"
              type="submit"
              disabled={!password || busy === "login"}
            >
              {busy === "login" ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <LockKeyhole size={17} />
              )}
              登录
            </button>
          </form>
          {error && <div className="admin-alert error">{error}</div>}
          <Link className="admin-back-link" href="/">
            <ArrowLeft size={15} />
            返回问答
          </Link>
        </section>
      </main>
    );
  }

  return (
    <main className="admin-shell">
      <header className="topbar">
        <div className="brand">
          <FileText size={22} />
          文档管理
        </div>
        <div className="admin-header-actions">
          <Link className="admin-back-link" href="/">
            <ArrowLeft size={15} />
            问答工作台
          </Link>
          <button className="admin-icon-button" type="button" onClick={logout}>
            <LogOut size={17} />
            退出
          </button>
        </div>
      </header>

      <div className="admin-content">
        <section className="admin-upload-band">
          <div>
            <h1>文档导入</h1>
            <p>选择 PDF 后先检查产品、版本和冲突，再进入索引队列。</p>
          </div>
          <form className="admin-upload-form" onSubmit={uploadSelected}>
            <input
              ref={fileInputRef}
              className="admin-file-input"
              id="manual-files"
              name="files"
              type="file"
              accept=".pdf,application/pdf"
              multiple
              onChange={(event) =>
                acceptFiles(event.target.files, "文件")
              }
            />
            <input
              ref={directoryInputRef}
              className="admin-file-input"
              id="manual-directory"
              name="directory-files"
              type="file"
              accept=".pdf,application/pdf"
              multiple
              onChange={(event) =>
                acceptFiles(event.target.files, "目录")
              }
            />
            <button
              className="admin-secondary-button"
              type="button"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload size={17} />
              选择文件
            </button>
            <button
              className="admin-secondary-button"
              type="button"
              onClick={() => directoryInputRef.current?.click()}
            >
              <FolderOpen size={17} />
              选择目录
            </button>
            <button
              className="admin-primary-button"
              type="submit"
              disabled={!selectedFiles.length || busy === "upload"}
            >
              {busy === "upload" ? (
                <LoaderCircle className="spin" size={17} />
              ) : (
                <Upload size={17} />
              )}
              上传 {selectedFiles.length || ""}
            </button>
          </form>
        </section>

        {(message || error) && (
          <div
            className={`admin-alert ${error ? "error" : "success"}`}
            role="status"
          >
            {error ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
            {error || message}
          </div>
        )}

        {batches.length > 0 && (
          <section className="admin-history">
            <div className="section-label">导入批次历史</div>
            <div className="admin-history-list">
              {batches.slice(0, 6).map((item) => (
                <button
                  type="button"
                  key={item.batch_id}
                  onClick={() => void loadBatch(item.batch_id)}
                >
                  <code>{item.batch_id.slice(0, 10)}</code>
                  <span>{item.item_count} 个文件</span>
                </button>
              ))}
            </div>
          </section>
        )}

        {batch ? (
          <>
            <section className="admin-batch">
              <div className="admin-batch-head">
                <div>
                  <div className="section-label">导入批次</div>
                  <strong>{batch.batch_id.slice(0, 12)}</strong>
                  <span>{batch.items.length} 个文件</span>
                </div>
                <button
                  className="admin-secondary-button"
                  type="button"
                  onClick={refresh}
                  disabled={busy === "refresh"}
                >
                  <RefreshCw
                    className={busy === "refresh" ? "spin" : undefined}
                    size={16}
                  />
                  刷新
                </button>
              </div>

              <div className="admin-list-heading">
                <strong>排队列表</strong>
                <span>{queueItems.length} 个文件</span>
              </div>
              {queueItems.length ? (
                <div className="admin-table-wrap">
                  <table className="admin-table admin-queue-table">
                    <thead>
                      <tr>
                        <th>文件名称</th>
                        <th>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      {queueItems.map((item) => (
                        <tr key={item.item_id}>
                          <td>
                            <div className="admin-file-cell">
                              <FileText size={16} />
                              <span>{item.filename}</span>
                            </div>
                          </td>
                          <td>
                            <span className={`admin-tag status-${item.status}`}>
                              {statusLabels[item.status] ?? item.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="admin-empty compact">
                  <span>暂无排队文件</span>
                </div>
              )}
            </section>

            <section className="admin-batch">
              <div className="admin-list-heading">
                <strong>文件列表</strong>
                <span>
                  {fileItems.length} 个文件 · {conflicts.length} 个冲突
                </span>
              </div>
              {fileItems.length ? (
                <div className="admin-table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>文件名称</th>
                        <th>产品</th>
                        <th>版本</th>
                        <th>置信度</th>
                        <th>冲突</th>
                        <th aria-label="操作" />
                      </tr>
                    </thead>
                    <tbody>
                      {fileItems.map((item) => (
                        <tr key={item.item_id}>
                          <td>
                            <div className="admin-file-cell">
                              <FileText size={16} />
                              <span>{item.filename}</span>
                            </div>
                            <code>{item.sha256.slice(0, 10)}</code>
                          </td>
                          <td>
                            {item.product_ids
                              .map(productLabel)
                              .join(", ") || "未识别"}
                          </td>
                          <td>{item.version_label ?? "未知"}</td>
                          <td>
                            <span
                              className={`admin-tag confidence-${item.confidence}`}
                            >
                              {confidenceLabels[item.confidence] ??
                                item.confidence}
                            </span>
                          </td>
                          <td>
                            {item.conflict_type
                              ? `是 · ${
                                  conflictLabels[item.conflict_type] ??
                                  item.conflict_type
                                }`
                              : "否"}
                          </td>
                          <td>
                            <div className="admin-row-actions">
                              {item.conflict_type !==
                                "duplicate_content" && (
                                <button
                                  type="button"
                                  onClick={() => void requestQueue(item)}
                                  disabled={busy === item.item_id}
                                >
                                  {busy === item.item_id ? (
                                    <LoaderCircle
                                      className="spin"
                                      size={14}
                                    />
                                  ) : (
                                    <ListPlus size={14} />
                                  )}
                                  加入排队列表
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => void cancelItem(item)}
                                disabled={busy === item.item_id}
                              >
                                <Trash2 size={14} />
                                取消
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="admin-empty compact">
                  <span>暂无待处理文件</span>
                </div>
              )}
            </section>
          </>
        ) : (
          <section className="admin-empty">
            <FileText size={30} strokeWidth={1.7} />
            <strong>还没有导入批次</strong>
            <span>选择单个 PDF 或整个目录开始。</span>
          </section>
        )}

        <section className="admin-batch admin-versions">
          <div className="admin-batch-head">
            <div>
              <div className="section-label">文档版本</div>
              <strong>审批与发布</strong>
              <span>索引完成并不代表已经进入问答检索</span>
            </div>
            <div className="admin-version-actions">
              <select
                className="admin-inline-select"
                aria-label="版本产品"
                value={versionProductId}
                onChange={(event) => {
                  setVersions([]);
                  setVersionProductId(event.target.value);
                }}
              >
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.display_name}
                  </option>
                ))}
              </select>
              <button
                className="admin-secondary-button"
                type="button"
                onClick={() => void loadVersions(versionProductId)}
                disabled={!versionProductId || versionsBusy}
              >
                <RefreshCw
                  className={versionsBusy ? "spin" : undefined}
                  size={16}
                />
                刷新
              </button>
            </div>
          </div>

          {renderVersionGroup("pending", pendingVersions)}
          {renderVersionGroup("approved", approvedVersions)}
        </section>
      </div>

      {productItem && (
        <div className="admin-modal-backdrop" role="presentation">
          <section
            className="admin-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="product-title"
          >
            <h2 className="admin-modal-title" id="product-title">
              <FileText size={19} />
              填写产品名称
            </h2>
            <p>
              “{productItem.filename}”未识别出产品。输入产品名称后加入排队列表；
              已存在则复用，不存在则自动创建新产品。
            </p>
            {productItem.detected_product_name && (
              <div className="admin-modal-meta">
                模型候选：{productItem.detected_product_name}
              </div>
            )}
            <label className="admin-modal-field" htmlFor="product-name">
              产品名称
            </label>
            <input
              className="admin-text-input"
              id="product-name"
              list="admin-product-options"
              value={productInput}
              onChange={(event) => setProductInput(event.target.value)}
              placeholder="例如：华为平板 C7 或 C7"
              autoFocus
              onKeyDown={(event) => {
                if (event.key === "Enter") confirmProduct();
              }}
            />
            <datalist id="admin-product-options">
              {products.map((product) => (
                <option key={product.id} value={product.display_name} />
              ))}
            </datalist>
            {error && <div className="admin-modal-error">{error}</div>}
            <div className="admin-modal-actions">
              <button
                className="admin-primary-button"
                type="button"
                onClick={confirmProduct}
                disabled={!productInput.trim()}
              >
                确认
              </button>
              <button
                className="admin-secondary-button"
                type="button"
                onClick={() => {
                  setProductItem(null);
                  setProductInput("");
                  setError("");
                }}
              >
                取消
              </button>
            </div>
          </section>
        </div>
      )}

      {conflictItem && (
        <div className="admin-modal-backdrop" role="presentation">
          <section
            className="admin-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="conflict-title"
          >
            <h2 className="admin-modal-title" id="conflict-title">
              <AlertTriangle size={19} />
              文件冲突
            </h2>
            <p>
              “{conflictItem.filename}”与已有文件同名但内容不同。
              覆盖后旧文件保留，新版本索引成功时会删除旧版本的向量数据。
            </p>
            {conflictItem.conflict_version_label && (
              <div className="admin-modal-meta">
                当前版本：{conflictItem.conflict_version_label}
              </div>
            )}
            <label className="admin-modal-field" htmlFor="new-version">
              新版本号
            </label>
            <input
              className="admin-text-input"
              id="new-version"
              value={conflictVersion}
              onChange={(event) => setConflictVersion(event.target.value)}
              placeholder="必须与旧版本不同"
            />
            {error && <div className="admin-modal-error">{error}</div>}
            <div className="admin-modal-actions">
              <button
                className="admin-primary-button"
                type="button"
                onClick={() => void overwriteItem()}
                disabled={busy === conflictItem.item_id}
              >
                {busy === conflictItem.item_id ? (
                  <LoaderCircle className="spin" size={15} />
                ) : null}
                覆盖
              </button>
              <button
                className="admin-secondary-button"
                type="button"
                onClick={() => void cancelItem(conflictItem)}
                disabled={busy === conflictItem.item_id}
              >
                <X size={15} />
                取消上传
              </button>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}
