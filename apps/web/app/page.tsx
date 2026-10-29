"use client";

import {
  BookOpen,
  FileStack,
  LoaderCircle,
  MessageSquareText,
  Plus,
  Send,
  ShieldAlert,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useRef, useState } from "react";

type Product = {
  id: string;
  display_name: string;
  category: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode?: string;
  serverId?: string;
  citations?: Citation[];
};

type Citation = {
  chunk_id: string;
  page: number;
  content: string;
  document_name?: string | null;
  version_label?: string | null;
  section_path?: string[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

function createId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function eventRows(block: string) {
  const event = block
    .split("\n")
    .find((line) => line.startsWith("event: "))
    ?.slice(7);
  const data = block
    .split("\n")
    .filter((line) => line.startsWith("data: "))
    .map((line) => line.slice(6))
    .join("\n");
  return { event, data };
}

async function responseError(response: Response) {
  const body = (await response.json().catch(() => null)) as {
    detail?: string | { message?: string };
  } | null;
  if (typeof body?.detail === "string") return body.detail;
  if (body?.detail?.message) return body.detail.message;
  return `HTTP ${response.status}`;
}

export default function Home() {
  const [products, setProducts] = useState<Product[]>([]);
  const [productId, setProductId] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [status, setStatus] = useState("选择产品后开始提问");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/products`)
      .then((response) => response.json())
      .then((items: Product[]) => {
        setProducts(items);
      })
      .catch(() => setStatus("产品目录加载失败"));
    fetch(`${API_BASE}/api/conversations`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(await responseError(response));
        }
        const payload = (await response.json()) as {
          conversation_id: string;
        };
        setConversationId(payload.conversation_id);
      })
      .catch(() => setStatus("无法创建会话"));
  }, []);

  useEffect(() => {
    if (!conversationId || !productId) return;
    fetch(
      `${API_BASE}/api/conversations/${conversationId}/resolve-product`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ product_id: productId }),
      },
    ).catch(() => setStatus("产品切换失败"));
  }, [conversationId, productId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const currentProduct = products.find((item) => item.id === productId);

  async function resetConversation() {
    setMessages([]);
    setStatus("正在建立新会话");
    try {
      const response = await fetch(`${API_BASE}/api/conversations`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error(await responseError(response));
      }
      const payload = (await response.json()) as {
        conversation_id: string;
      };
      setConversationId(payload.conversation_id);
      setStatus("新会话已建立");
    } catch (error) {
      setStatus(
        error instanceof Error ? error.message : "新会话创建失败",
      );
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const question = input.trim();
    if (!question || busy) return;

    setInput("");
    setBusy(true);
    setStatus("正在检索手册");
    const userMessage: ChatMessage = {
      id: createId(),
      role: "user",
      content: question,
    };
    const assistantId = createId();
    if (!conversationId) {
      setStatus("会话尚未创建");
      return;
    }
    const activeConversationId = conversationId;
    setMessages((items) => [
      ...items,
      userMessage,
      { id: assistantId, role: "assistant", content: "", citations: [] },
    ]);

    try {
      const requestBody: { question: string; product_id?: string } = {
        question,
      };
      if (productId) requestBody.product_id = productId;

      const response = await fetch(
        `${API_BASE}/api/conversations/${activeConversationId}/messages/stream`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(requestBody),
        },
      );
      if (!response.ok || !response.body) {
        const errorBody = (await response.json().catch(() => null)) as {
          detail?: { message?: string } | string;
        } | null;
        const detail =
          typeof errorBody?.detail === "string"
            ? errorBody.detail
            : errorBody?.detail?.message;
        throw new Error(detail ?? `HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finished = false;

      while (!finished) {
        const chunk = await reader.read();
        finished = chunk.done;
        buffer += decoder.decode(chunk.value ?? new Uint8Array(), {
          stream: !finished,
        });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";

        for (const block of blocks) {
          const { event: name, data } = eventRows(block);
          if (!name || !data) continue;
          const payload = JSON.parse(data) as Record<string, unknown>;

          if (name === "status") {
            const stages: Record<string, string> = {
              retrieving: "正在检索手册",
              reranking: "正在筛选证据",
              generating: "正在生成回答",
              verifying: "正在核对引用",
              retrying: "正在补充检索",
              clarifying: "请补充设备信息",
            };
            setStatus(stages[String(payload.stage)] ?? "正在处理");
          }

          if (name === "error") {
            throw new Error(
              String(payload.message ?? "回答生成失败"),
            );
          }

          if (name === "answer_delta") {
            const text = String(payload.text ?? "");
            setMessages((items) =>
              items.map((item) =>
                item.id === assistantId
                  ? { ...item, content: item.content + text }
                  : item,
              ),
            );
          }

          if (name === "citations") {
            const citations = Array.isArray(payload.items)
              ? (payload.items as Citation[]).filter(
                  (item) =>
                    typeof item.chunk_id === "string" &&
                    typeof item.page === "number" &&
                    typeof item.content === "string",
                )
              : [];
            setMessages((items) =>
              items.map((item) =>
                item.id === assistantId ? { ...item, citations } : item,
              ),
            );
          }

          if (name === "done") {
            const mode = String(payload.mode ?? "manual_grounded");
            setMessages((items) =>
              items.map((item) =>
                item.id === assistantId
                  ? {
                      ...item,
                      mode,
                      serverId:
                        typeof payload.message_id === "string"
                          ? payload.message_id
                          : undefined,
                    }
                  : item,
              ),
            );
            setStatus("回答完成");
          }
        }
      }
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "回答失败";
      setStatus(message);
      setMessages((items) =>
        items.map((item) =>
          item.id === assistantId
            ? {
                ...item,
                content:
                  message.includes("选择产品") || message.includes("型号")
                    ? "请在问题中写明产品型号，或先在左侧选择产品。"
                    : `暂时无法完成回答：${message}`,
              }
            : item,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  async function rateAnswer(
    message: ChatMessage,
    rating: "helpful" | "not_helpful",
  ) {
    if (!conversationId || !message.serverId) return;
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/messages/${message.serverId}/feedback`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rating, reason: null }),
      },
    );
    if (!response.ok) {
      setStatus(await responseError(response));
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <BookOpen size={22} />
          <span>产品手册助手</span>
        </div>
        <div className="topbar-actions">
          <div className="service-state">
            <span className="status-dot" />
            API 已连接
          </div>
          <Link className="admin-entry" href="/admin">
            <FileStack size={16} />
            文档管理
          </Link>
        </div>
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <div className="section-label">当前产品</div>
          <select
            id="product-select"
            name="product_id"
            className="product-select"
            aria-label="选择产品"
            value={productId}
            onChange={(event) => {
              setProductId(event.target.value);
              void resetConversation();
            }}
          >
            <option value="">自动识别产品</option>
            {products.map((product) => (
              <option key={product.id} value={product.id}>
                {product.display_name}
              </option>
            ))}
          </select>

          <div className="product-meta">
            <span>{currentProduct?.category ?? "自动识别"}</span>
            <span>{conversationId.slice(0, 8)}</span>
          </div>

          <button
            className="new-chat"
            type="button"
            onClick={() => void resetConversation()}
          >
            <Plus size={17} />
            新建会话
          </button>

          <div className="scope-note">
            <ShieldAlert size={17} />
            <p>安全相关问题仅依据当前产品手册回答。</p>
          </div>
        </aside>

        <section className="chat-pane">
          <div className="chat-scroll">
            {messages.length === 0 ? (
              <div className="empty-state">
                <MessageSquareText size={34} strokeWidth={1.7} />
                <h1>从手册里找答案</h1>
                <p>先选择产品，再询问接口、设置、操作或安全信息。</p>
              </div>
            ) : (
              messages.map((message) => (
                <article
                  className={`message ${message.role}`}
                  key={message.id}
                >
                  <div className="message-role">
                    {message.role === "user" ? "你" : "产品手册助手"}
                    {message.mode && (
                      <span className="mode">
                        {message.mode === "manual_grounded"
                          ? "手册依据"
                          : message.mode === "general_explanation"
                            ? "通用说明"
                            : message.mode === "clarification"
                              ? "需要澄清"
                              : "已拒答"}
                      </span>
                    )}
                  </div>
                  <div className="message-content">
                    {message.content || (busy ? "正在处理..." : "")}
                  </div>
                  {!!message.citations?.length && (
                    <div className="citation-list">
                      {message.citations.map((citation, index) => (
                        <details className="citation" key={citation.chunk_id}>
                          <summary>
                            引用 {index + 1} ·{" "}
                            {citation.document_name ?? "手册"} ·{" "}
                            {citation.version_label
                              ? `版本 ${citation.version_label}`
                              : "版本未知"}{" "}
                            · 第 {citation.page} 页
                          </summary>
                          {citation.section_path?.length ? (
                            <div className="citation-path">
                              {citation.section_path.join(" / ")}
                            </div>
                          ) : null}
                          <p>{citation.content}</p>
                        </details>
                      ))}
                    </div>
                  )}
                  {message.role === "assistant" &&
                    message.serverId && (
                      <div className="feedback-actions">
                        <button
                          type="button"
                          aria-label="回答有帮助"
                          title="回答有帮助"
                          onClick={() =>
                            void rateAnswer(message, "helpful")
                          }
                        >
                          <ThumbsUp size={14} />
                        </button>
                        <button
                          type="button"
                          aria-label="回答没有帮助"
                          title="回答没有帮助"
                          onClick={() =>
                            void rateAnswer(message, "not_helpful")
                          }
                        >
                          <ThumbsDown size={14} />
                        </button>
                      </div>
                    )}
                </article>
              ))
            )}
            <div ref={bottomRef} />
          </div>

          <form className="composer" onSubmit={submit}>
            <div className="status-line">
              {busy && <LoaderCircle className="spin" size={15} />}
              {status}
            </div>
            <div className="input-row">
              <textarea
                id="chat-question"
                name="question"
                aria-label="输入问题"
                placeholder="例如：B5-341W 有哪些视频接口？"
                rows={2}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
              />
              <button
                className="send-button"
                type="submit"
                disabled={busy || !input.trim()}
                aria-label="发送问题"
              >
                <Send size={19} />
              </button>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}
