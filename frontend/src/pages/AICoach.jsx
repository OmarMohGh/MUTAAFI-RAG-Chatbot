/**
 * =========================================================================
 * AICoach.jsx — RAG-Powered AI Fitness Chatbot Interface
 * =========================================================================
 *
 * PURPOSE:
 *   Provides a real-time chat UI where the authenticated user can ask
 *   questions about fitness, nutrition, and their workout/meal plans.
 *   Messages are sent to the Flask backend's /api/chat endpoint, which
 *   uses a Retrieval-Augmented Generation (RAG) pipeline to return
 *   answers grounded in the Mutaafi knowledge base.
 *
 * FEATURE / PAGE:
 *   AI Coach — accessible from the main sidebar after login.
 *
 * BACKEND CONNECTION:
 *   - POST /api/chat  — Sends the user's message (with an optional JWT
 *     Bearer token for personalised context) and receives an AI-generated
 *     reply plus optional source citations.
 *   - supabase.auth.getSession() — Retrieves the current JWT token so
 *     the backend can look up the user's profile for personalisation.
 *
 * RELATED COMPONENTS:
 *   - ReactMarkdown  — Renders the AI's response as formatted Markdown
 *     (headings, lists, bold, links, code blocks, etc.).
 *   - App.jsx router — Mounts this component at the '/ai-coach' route.
 * =========================================================================
 */

// ======================= IMPORTS =======================
// Core React hooks
import { useState, useRef, useEffect } from 'react';
// Lucide send-arrow icon for the submit button
import { Send } from 'lucide-react';
// Markdown renderer for rich AI responses
import ReactMarkdown from 'react-markdown';
// Supabase client for auth session retrieval
import { supabase } from '../supabaseClient';

// ======================= COMPONENT =======================
/**
 * AICoach — full-screen chat interface for the RAG fitness chatbot.
 *
 * @returns {JSX.Element} A vertically stacked layout with a header,
 *          scrollable message area, and a fixed input bar at the bottom.
 */
const AICoach = () => {

  // ======================= STATE & HOOKS =======================

  // Array of chat messages; each object has { role, content, sources? }
  const [messages, setMessages] = useState([]);

  // Current text in the input field (controlled component)
  const [input, setInput] = useState('');

  // Whether the AI is currently generating a response
  const [loading, setLoading] = useState(false);

  // Ref to an invisible div at the bottom of the message list — used for auto-scroll
  const messagesEndRef = useRef(null);

  /**
   * Smoothly scrolls the chat window to the bottom so the latest
   * message is always visible.
   *
   * @returns {void}
   */
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Set the page title and auto-scroll whenever messages change or loading toggles
  useEffect(() => {
    document.title = "AI Coach | Mutaafi";
    scrollToBottom();
  }, [messages, loading]);

  // ======================= EVENT HANDLERS =======================

  /**
   * Sends the user's message to the Flask /api/chat endpoint and
   * appends the AI's reply to the message list.
   *
   * Workflow:
   *   1. Trims and validates the input text.
   *   2. Pushes the user's message bubble into state immediately.
   *   3. Retrieves the current Supabase JWT for personalised responses.
   *   4. Calls POST /api/chat with the message and auth token.
   *   5. Pushes the AI reply (with optional source citations) into state.
   *   6. On error, pushes a friendly error bubble instead.
   *
   * @param {React.FormEvent} e — The form submit event.
   * @returns {Promise<void>}
   *
   * Triggered when the user presses Enter or clicks the send button.
   */
  const handleSend = async (e) => {
    e.preventDefault();
    const userText = input.trim();
    if (!userText || loading) return;

    // Push user message into the chat immediately
    setMessages(prev => [...prev, { role: 'user', content: userText }]);
    setInput('');
    setLoading(true);

    try {
      // Get the current user's JWT token (if logged in) for personalisation
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      const response = await fetch('http://127.0.0.1:5000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify({ message: userText })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to get response');
      }

      // Append the AI's reply with optional source citations
      setMessages(prev => [...prev, {
        role: 'ai',
        content: data.reply,
        sources: data.sources || ''
      }]);
    } catch (err) {
      // Show a user-friendly error bubble in the chat
      setMessages(prev => [...prev, {
        role: 'ai',
        content: `Sorry, I encountered an error: ${err.message}`,
        sources: ''
      }]);
    } finally {
      setLoading(false);
    }
  };

  // ======================= RETURN (JSX) =======================
  return (
    <div className="max-w-4xl mx-auto flex flex-col h-[calc(100vh-7rem)]">

      {/* ---------- HEADER ---------- */}
      <div className="text-center pb-4 border-b border-gray-200 dark:border-gray-800 mb-4">
        <h1 className="text-2xl font-bold text-[#2a3441] dark:text-gray-100">Ask Your Coach</h1>
        {/* Online status indicator with pulsing dot */}
        <div className="flex items-center justify-center mt-2 space-x-2">
          <span className="w-2.5 h-2.5 bg-[#108a6e] dark:bg-[#19cba3] rounded-full inline-block animate-pulse"></span>
          <span className="text-sm text-gray-500 dark:text-gray-400">Fitness AI Bot (Online)</span>
        </div>
      </div>

      {/* ---------- CHAT MESSAGES AREA (scrollable) ---------- */}
      <div className="flex-1 overflow-y-auto px-2 space-y-4 pb-4">

        {/* Empty state — shown when no messages exist yet */}
        {messages.length === 0 && !loading && (
          <div className="text-center text-gray-400 dark:text-gray-500 mt-20 text-sm">
            Ask me anything about fitness, nutrition, or your workout plan!
          </div>
        )}

        {/* Render each message bubble */}
        {messages.map((msg, index) => (
          <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'user' ? (
              /* User bubble (right-aligned, green background) */
              <div className="max-w-[70%]">
                <div className="bg-[#108a6e] text-white px-5 py-3 rounded-2xl rounded-tr-sm shadow-sm">
                  <p className="text-sm leading-relaxed">{msg.content}</p>
                </div>
                <p className="text-right text-[10px] text-gray-400 dark:text-gray-500 mt-1 mr-1">You</p>
              </div>
            ) : (
              /* AI bubble (left-aligned, card style) — renders markdown */
              <div className="max-w-[80%]">
                <div className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 px-5 py-4 rounded-2xl rounded-tl-sm shadow-sm">
                  <p className="text-xs font-bold text-[#2a3441] dark:text-gray-100 mb-2">AI Coach:</p>

                  {/* Markdown-rendered AI response */}
                  <div className="ai-markdown text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                    <ReactMarkdown
                      components={{
                        a: ({ node, ...props }) => (
                          <a {...props} target="_blank" rel="noopener noreferrer"
                            className="text-[#108a6e] dark:text-[#19cba3] underline hover:opacity-80" />
                        ),
                        p: ({ node, ...props }) => <p {...props} className="mb-2 last:mb-0" />,
                        ul: ({ node, ...props }) => <ul {...props} className="list-disc pl-5 mb-2 space-y-1" />,
                        ol: ({ node, ...props }) => <ol {...props} className="list-decimal pl-5 mb-2 space-y-1" />,
                        li: ({ node, ...props }) => <li {...props} className="text-sm" />,
                        strong: ({ node, ...props }) => <strong {...props} className="font-semibold text-gray-800 dark:text-gray-100" />,
                        em: ({ node, ...props }) => <em {...props} className="italic" />,
                        h1: ({ node, ...props }) => <h1 {...props} className="text-base font-bold mb-1" />,
                        h2: ({ node, ...props }) => <h2 {...props} className="text-sm font-bold mb-1" />,
                        h3: ({ node, ...props }) => <h3 {...props} className="text-sm font-semibold mb-1" />,
                        code: ({ node, inline, ...props }) =>
                          inline
                            ? <code {...props} className="bg-gray-100 dark:bg-gray-700 px-1.5 py-0.5 rounded text-xs font-mono" />
                            : <code {...props} className="block bg-gray-100 dark:bg-gray-700 p-3 rounded-lg text-xs font-mono overflow-x-auto mb-2" />,
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>

                  {/* Source citation footer (only shown when sources exist) */}
                  {msg.sources && (
                    <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-3 border-t border-gray-100 dark:border-gray-700 pt-2">
                      Source: <span className="italic">{msg.sources}</span>
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}

        {/* Typing indicator — three bouncing dots shown while AI is responding */}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 px-5 py-4 rounded-2xl rounded-tl-sm shadow-sm max-w-[80%]">
              <p className="text-xs font-bold text-[#2a3441] dark:text-gray-100 mb-2">AI Coach:</p>
              <div className="flex space-x-1.5 items-center h-5">
                <span className="w-2 h-2 bg-[#108a6e] dark:bg-[#19cba3] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                <span className="w-2 h-2 bg-[#108a6e] dark:bg-[#19cba3] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                <span className="w-2 h-2 bg-[#108a6e] dark:bg-[#19cba3] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
              </div>
            </div>
          </div>
        )}

        {/* Invisible scroll anchor — scrollToBottom targets this element */}
        <div ref={messagesEndRef} />
      </div>

      {/* ---------- FIXED INPUT BAR ---------- */}
      <div className="border-t border-gray-200 dark:border-gray-800 pt-4 pb-2 bg-[#f8f9fa] dark:bg-gray-950">
        <form onSubmit={handleSend} className="flex items-center space-x-3">
          {/* Text input for the user's question */}
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your question here..."
            disabled={loading}
            className="flex-1 px-5 py-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-full focus:outline-none focus:ring-2 focus:ring-[#108a6e] focus:border-transparent text-sm text-gray-700 dark:text-gray-100 shadow-sm disabled:opacity-50"
          />

          {/* Send button — disabled when input is empty or AI is loading */}
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className={`bg-[#108a6e] text-white p-3 rounded-full shadow-sm hover:bg-[#0c6954] transition-colors ${(loading || !input.trim()) ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
};

// ======================= EXPORT =======================
export default AICoach;
