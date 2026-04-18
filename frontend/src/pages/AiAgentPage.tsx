import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { PageShell } from "../components/PageShell";
import { PropertySelector } from "../components/PropertySelector";
import { SectionCard } from "../components/SectionCard";
import { usePropertyStore } from "../stores/useProperty";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type ChatSession = {
  id: string;
  title: string;
  messages: ChatMessage[];
};

const STORAGE_KEY = "dmrb-ai-sessions";
const SUGGESTIONS = [
  "Give me the morning briefing",
  "Which units are highest risk right now?",
  "What should I verify before trusting today's imports?",
  "Which units look stalled?",
];

function loadSessions(): ChatSession[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as ChatSession[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function AiAgentPage() {
  const propertyId = usePropertyStore((state) => state.propertyId);
  const [sessions, setSessions] = useState<ChatSession[]>(() => loadSessions());
  const [activeId, setActiveId] = useState<string | null>(sessions[0]?.id ?? null);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  }, [sessions]);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeId) ?? null,
    [activeId, sessions],
  );

  const upsertSession = (next: ChatSession) => {
    setSessions((current) => {
      const exists = current.some((session) => session.id === next.id);
      if (exists) {
        return current.map((session) => (session.id === next.id ? next : session));
      }
      return [next, ...current];
    });
    setActiveId(next.id);
  };

  const ensureSession = (): ChatSession => {
    if (activeSession) {
      return activeSession;
    }
    const next = {
      id: `${Date.now()}`,
      title: "New Chat",
      messages: [],
    };
    upsertSession(next);
    return next;
  };

  const sendPrompt = (prompt: string) => {
    if (!prompt.trim() || !propertyId || streaming) {
      return;
    }
    const session = ensureSession();
    const nextMessages: ChatMessage[] = [
      ...session.messages,
      { role: "user", content: prompt.trim() },
      { role: "assistant", content: "" },
    ];
    const nextSession: ChatSession = {
      ...session,
      title: session.messages.length ? session.title : prompt.trim().slice(0, 40),
      messages: nextMessages,
    };
    upsertSession(nextSession);
    setDraft("");
    setStreaming(true);

    const history = encodeURIComponent(JSON.stringify(session.messages));
    const url = `/api/operations/ai/stream?property_id=${propertyId}&message=${encodeURIComponent(prompt.trim())}&history=${history}`;
    const source = new EventSource(url);

    source.onmessage = (event) => {
      const payload = JSON.parse(event.data) as { type: string; content?: string; message?: string };
      if (payload.type === "chunk" && payload.content) {
        setSessions((current) =>
          current.map((item) => {
            if (item.id !== nextSession.id) {
              return item;
            }
            const messages = [...item.messages];
            const last = messages[messages.length - 1];
            messages[messages.length - 1] = { role: "assistant", content: `${last.content}${payload.content}` };
            return { ...item, messages };
          }),
        );
      }
      if (payload.type === "done") {
        source.close();
        setStreaming(false);
      }
      if (payload.type === "error") {
        source.close();
        setStreaming(false);
        toast.error(payload.message ?? "AI request failed");
      }
    };

    source.onerror = () => {
      source.close();
      setStreaming(false);
      toast.error("AI stream disconnected");
    };
  };

  return (
    <PageShell
      title="AI Agent"
      description="Ask questions about your portfolio and get answers."
      action={<PropertySelector />}
    >
      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <SectionCard
          title="Sessions"
          actions={
            <button
              type="button"
              onClick={() => {
                const next = { id: `${Date.now()}`, title: "New Chat", messages: [] as ChatMessage[] };
                upsertSession(next);
              }}
              className="btn-primary"
            >
              New Chat
            </button>
          }
        >
          <div className="space-y-2">
            {sessions.length ? (
              sessions.map((session) => (
                <div key={session.id} className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setActiveId(session.id)}
                    className={`flex-1 truncate rounded-lg border px-3 py-2 text-left text-sm transition ${
                      activeId === session.id
                        ? "border-border-strong bg-surface-3 text-text-strong"
                        : "border-border bg-surface-2 text-muted hover:text-text"
                    }`}
                  >
                    {session.title}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSessions((current) => current.filter((item) => item.id !== session.id));
                      if (activeId === session.id) {
                        setActiveId(null);
                      }
                    }}
                    className="btn-ghost"
                  >
                    Delete
                  </button>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted">No sessions yet.</p>
            )}
          </div>
        </SectionCard>

        <SectionCard title="Conversation" description="AI can make mistakes. Check important info.">
          {activeSession?.messages.length ? (
            <div className="space-y-4">
              {activeSession.messages.map((message, index) => (
                <div
                  key={`${message.role}-${index}`}
                  className={`max-w-3xl rounded-2xl px-4 py-3 text-sm ${
                    message.role === "user"
                      ? "ml-auto bg-surface-3 text-text-strong"
                      : "border border-border bg-surface-2 text-text"
                  }`}
                >
                  {message.content || (streaming && message.role === "assistant" ? "..." : "")}
                </div>
              ))}
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => sendPrompt(suggestion)}
                  className="rounded-xl border border-border bg-surface-2 px-4 py-4 text-left text-sm text-text transition hover:border-border-strong hover:bg-surface-3"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}

          <div className="mt-6 flex gap-3">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask anything about turnovers..."
              className="input flex-1"
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  sendPrompt(draft);
                }
              }}
            />
            <button
              type="button"
              onClick={() => sendPrompt(draft)}
              disabled={streaming}
              className="btn-primary"
            >
              {streaming ? "Streaming..." : "Send"}
            </button>
          </div>
        </SectionCard>
      </div>
    </PageShell>
  );
}
