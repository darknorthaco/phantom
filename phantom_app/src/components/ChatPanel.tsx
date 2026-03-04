import { useState, useRef, useEffect } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

const CONTROLLER = 'http://127.0.0.1:8080';

function timestamp(): string {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'welcome',
      role: 'system',
      content:
        'Phantom Chat routes your questions to a local language model running on your own GPU. ' +
        'No data leaves your network. To get started, deploy a model worker via the Workers panel, ' +
        'then type your question below.',
      timestamp: timestamp(),
    },
  ]);
  const [input, setInput]       = useState('');
  const [loading, setLoading]   = useState(false);
  const [model, setModel]       = useState('phi-3.5-mini');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: timestamp(),
    };
    setMessages((m) => [...m, userMsg]);
    setLoading(true);

    try {
      // Submit as an inference task to the Phantom controller.
      // The LLM Task Master routes it to the best available worker.
      const response = await fetch(`${CONTROLLER}/tasks/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_type: 'llm_inference',
          parameters: {
            model,
            prompt: text,
            max_tokens: 512,
            temperature: 0.7,
          },
          priority: 1,
        }),
      });

      if (!response.ok) {
        throw new Error(`Controller returned ${response.status}`);
      }

      const data = await response.json();
      const taskId: string = data.task_id;

      // Poll for the result (simple approach — WebSocket streaming is a future upgrade)
      const result = await pollTaskResult(taskId);

      const assistantMsg: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: result,
        timestamp: timestamp(),
      };
      setMessages((m) => [...m, assistantMsg]);
    } catch (err) {
      const errMsg: Message = {
        id: crypto.randomUUID(),
        role: 'system',
        content:
          `Could not reach the controller or no model worker is available. ` +
          `Make sure a worker with the "${model}" model is registered and online. ` +
          `Error: ${String(err)}`,
        timestamp: timestamp(),
      };
      setMessages((m) => [...m, errMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="panel-header">
        <span className="panel-title">Chat</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Model</span>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            style={{
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-dim)',
              color: 'var(--text-primary)',
              padding: '3px 6px',
              borderRadius: 4,
              fontSize: 11,
              fontFamily: 'var(--font-mono)',
            }}
          >
            <option value="phi-3.5-mini">Phi-3.5 Mini (3.8B)</option>
            <option value="llama-3-8b">Llama 3 (8B)</option>
            <option value="mistral-7b">Mistral (7B)</option>
            <option value="custom">Custom</option>
          </select>
        </div>
      </div>

      {/* Message thread */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
      }}>
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <div style={{
              maxWidth: '80%',
              padding: '8px 12px',
              borderRadius: 8,
              fontSize: 13,
              lineHeight: 1.6,
              background:
                msg.role === 'user'      ? 'var(--accent-blue)'  :
                msg.role === 'assistant' ? 'var(--bg-tertiary)'  :
                                           'var(--bg-secondary)',
              color:
                msg.role === 'user'      ? '#fff'                       :
                msg.role === 'assistant' ? 'var(--text-primary)'        :
                                           'var(--text-muted)',
              border: msg.role === 'system' ? '1px solid var(--border-dim)' : 'none',
              fontStyle: msg.role === 'system' ? 'italic' : 'normal',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {msg.content}
            </div>
            <span style={{
              fontSize: 9,
              color: 'var(--text-muted)',
              marginTop: 3,
              fontFamily: 'var(--font-mono)',
            }}>
              {msg.role !== 'system' && (msg.role === 'user' ? 'you' : 'phantom')} {msg.timestamp}
            </span>
          </div>
        ))}

        {loading && (
          <div style={{ display: 'flex', alignItems: 'flex-start' }}>
            <div style={{
              padding: '8px 14px',
              borderRadius: 8,
              background: 'var(--bg-tertiary)',
              fontSize: 13,
              color: 'var(--text-muted)',
              fontStyle: 'italic',
            }}>
              Routing to local model…
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div style={{
        padding: '10px 16px',
        borderTop: '1px solid var(--border-color)',
        display: 'flex',
        gap: 8,
      }}>
        <input
          type="text"
          placeholder="Ask anything — runs on your hardware, stays on your network"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send()}
          disabled={loading}
          style={{
            flex: 1,
            background: 'var(--bg-tertiary)',
            border: '1px solid var(--border-dim)',
            color: 'var(--text-primary)',
            padding: '8px 12px',
            borderRadius: 6,
            fontSize: 13,
            fontFamily: 'inherit',
            outline: 'none',
          }}
        />
        <button
          className="console-send-btn"
          onClick={send}
          disabled={loading || !input.trim()}
          style={{ padding: '8px 18px', fontSize: 12 }}
        >
          {loading ? '…' : 'Send'}
        </button>
      </div>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────────

async function pollTaskResult(taskId: string, maxWaitMs = 30_000): Promise<string> {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    await sleep(1_500);
    const r = await fetch(`${CONTROLLER}/tasks/${taskId}`);
    if (!r.ok) continue;
    const data = await r.json();
    if (data.status === 'completed' && data.result) {
      return typeof data.result === 'string'
        ? data.result
        : JSON.stringify(data.result, null, 2);
    }
    if (data.status === 'failed') {
      throw new Error(data.error ?? 'Task failed');
    }
  }
  throw new Error('Model took too long to respond (30s timeout). Is a worker online?');
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
