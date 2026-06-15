// Multi-turn water-planning advisor for one district. The user picks a goal,
// the model analyzes the location's prediction data, asks about their current
// position, and works toward a sustainable-usage plan. Conversation lives in
// component state only (no persistence) and resets when the panel switches
// district (the parent keys this component by district name).
import { useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { sendAdvisorChat } from '../../api/client.js';
import { ADVISOR_NEEDS, kickoffMessage } from '../../lib/advisor.js';

export default function AdvisorChat({ district, snapshot }) {
  const [need, setNeed] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const logRef = useRef(null);

  const mutation = useMutation({
    mutationFn: ({ messages: turns, need: needId }) =>
      sendAdvisorChat({ districtName: district, need: needId, snapshot, messages: turns }),
    onSuccess: (data) =>
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]),
  });

  // Keep the newest turn in view as the conversation grows.
  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [messages, mutation.isPending]);

  function startWithNeed(needId) {
    setNeed(needId);
    const first = [{ role: 'user', content: kickoffMessage(needId, district) }];
    setMessages(first);
    mutation.mutate({ messages: first, need: needId });
  }

  function send() {
    const text = input.trim();
    if (!text || mutation.isPending) return;
    const next = [...messages, { role: 'user', content: text }];
    setMessages(next);
    setInput('');
    mutation.mutate({ messages: next, need });
  }

  function handleKeyDown(event) {
    // Enter sends; Shift+Enter inserts a newline.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      send();
    }
  }

  // Goal picker — shown until a need is chosen.
  if (!need) {
    return (
      <div className="rounded-lg border border-ink/10 bg-paper/60 p-4">
        <p className="text-sm font-semibold">Plan your water use with AI</p>
        <p className="mt-1 text-xs text-ink-soft">
          Pick a goal. The advisor reviews {district}'s risk, forecast, and recharge
          data, asks about your situation, and builds a sustainable-usage plan.
        </p>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {ADVISOR_NEEDS.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => startWithNeed(option.id)}
              className="rounded-lg border border-ink/15 bg-surface px-3 py-2.5 text-left transition-colors hover:border-water hover:bg-water/5 focus-visible:outline-water"
            >
              <span className="block text-sm font-semibold">{option.label}</span>
              <span className="mt-0.5 block text-xs text-ink-soft">{option.blurb}</span>
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-ink/10 bg-paper/60 p-4">
      <div
        ref={logRef}
        className="panel-scroll max-h-72 space-y-3 overflow-y-auto"
        aria-live="polite"
        aria-label="Advisor conversation"
      >
        {messages.map((message, index) => (
          <ChatBubble key={index} role={message.role} content={message.content} />
        ))}
        {mutation.isPending && (
          <p className="text-xs italic text-ink-soft">The advisor is thinking…</p>
        )}
        {mutation.isError && (
          <p role="alert" className="text-xs font-medium text-risk-critical">
            The advisor is unavailable right now. Send your message again to retry.
          </p>
        )}
      </div>

      <div className="mt-3 flex items-end gap-2">
        <label htmlFor="advisor-input" className="sr-only">
          Reply to the advisor
        </label>
        <textarea
          id="advisor-input"
          rows={2}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={mutation.isPending}
          placeholder="Describe your situation (land size, crops, water source…)"
          className="min-h-[2.75rem] flex-1 resize-y rounded-lg border border-ink/15 bg-surface px-3 py-2 text-sm focus-visible:outline-water disabled:opacity-50"
        />
        <button
          type="button"
          onClick={send}
          disabled={mutation.isPending || !input.trim()}
          className="btn-primary !py-2 text-sm disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}

function ChatBubble({ role, content }) {
  const isUser = role === 'user';
  return (
    <div className={isUser ? 'flex justify-end' : 'flex justify-start'}>
      <div
        className={`max-w-[85%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm ${
          isUser ? 'bg-water/10 text-ink' : 'border border-ink/10 bg-surface text-ink'
        }`}
      >
        {content}
      </div>
    </div>
  );
}
