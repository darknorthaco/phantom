import { useState, useRef, useEffect } from 'react';

interface Message {
  id: number;
  type: 'system' | 'success' | 'error' | 'user';
  text: string;
  time: string;
}

export default function PhantomConsole() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 1,
      type: 'system',
      text: 'Phantom Distributed Compute Fabric — Controller online.',
      time: new Date().toLocaleTimeString(),
    },
    {
      id: 2,
      type: 'success',
      text: 'Engine active. Execution mode: AUTO. Awaiting commands.',
      time: new Date().toLocaleTimeString(),
    },
  ]);
  const [input, setInput] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const addMessage = (type: Message['type'], text: string) => {
    setMessages((prev) => [
      ...prev,
      { id: Date.now(), type, text, time: new Date().toLocaleTimeString() },
    ]);
  };

  const handleSend = () => {
    const cmd = input.trim();
    if (!cmd) return;
    setInput('');
    addMessage('user', cmd);

    if (cmd === 'health' || cmd === 'status') {
      addMessage('system', 'Querying controller health…');
      fetch('http://127.0.0.1:8080/health')
        .then((r) => r.json())
        .then((d) => addMessage('success', JSON.stringify(d, null, 2)))
        .catch((e) => addMessage('error', `Error: ${e}`));
    } else if (cmd === 'workers') {
      fetch('http://127.0.0.1:8080/workers')
        .then((r) => r.json())
        .then((d) => addMessage('success', JSON.stringify(d, null, 2)))
        .catch((e) => addMessage('error', `Error: ${e}`));
    } else if (cmd === 'stats') {
      fetch('http://127.0.0.1:8080/stats')
        .then((r) => r.json())
        .then((d) => addMessage('success', JSON.stringify(d, null, 2)))
        .catch((e) => addMessage('error', `Error: ${e}`));
    } else if (cmd === 'help') {
      addMessage('system', 'Commands: health, workers, stats, mode, help');
    } else if (cmd === 'mode') {
      fetch('http://127.0.0.1:8080/mode')
        .then((r) => r.json())
        .then((d) => addMessage('success', JSON.stringify(d, null, 2)))
        .catch((e) => addMessage('error', `Error: ${e}`));
    } else {
      addMessage('system', `Unknown command: ${cmd}. Type "help" for available commands.`);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSend();
  };

  return (
    <div className="console">
      <div className="console-messages">
        {messages.map((msg) => (
          <div key={msg.id} className={`console-msg ${msg.type}`}>
            <span className="timestamp">[{msg.time}]</span>
            <span style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</span>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <div className="console-input-row">
        <input
          className="console-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a command… (health, workers, stats, help)"
          spellCheck={false}
        />
        <button className="console-send-btn" onClick={handleSend}>
          Send
        </button>
      </div>
    </div>
  );
}
