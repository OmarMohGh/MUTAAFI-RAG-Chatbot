import { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { supabase } from '../supabaseClient';

const GlobalChatOverlay = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Auto-scroll to newest message
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, loading, isOpen]);

  const toggleChat = () => setIsOpen(!isOpen);

  const handleSend = async (e) => {
    e.preventDefault();
    const userText = input.trim();
    if (!userText || loading) return;

    setMessages(prev => [...prev, { role: 'user', content: userText }]);
    setInput('');
    setLoading(true);

    try {
      // Get the current user's JWT token (if logged in)
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

      setMessages(prev => [...prev, {
        role: 'ai',
        content: data.reply,
        sources: data.sources || ''
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        role: 'ai',
        content: `Sorry, I encountered an error: ${err.message}`,
        sources: ''
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {/* Chat Window */}
      <div 
        className={`bg-white dark:bg-gray-900 shadow-2xl rounded-2xl border border-gray-200 dark:border-gray-800 transition-all duration-300 transform origin-bottom-right mb-4 flex flex-col overflow-hidden w-[calc(100vw-2rem)] sm:w-[400px] h-[500px] max-h-[calc(100vh-6rem)] ${isOpen ? 'scale-100 opacity-100' : 'scale-0 opacity-0 pointer-events-none absolute right-0 bottom-16'}`}
      >
        {/* Header */}
        <div className="bg-[#10b981] text-white p-4 flex justify-between items-center shrink-0">
          <div>
            <h3 className="font-bold text-lg leading-tight">MUTAAFI AI Coach</h3>
            <p className="text-xs text-green-100">Online & ready to help</p>
          </div>
          <button 
            onClick={toggleChat}
            className="hover:bg-white/20 p-1 rounded-full transition-colors focus:outline-none"
            title="Close chat"
          >
            <X size={20} />
          </button>
        </div>

        {/* Message Area */}
        <div className="flex-1 overflow-y-auto p-4 bg-gray-50 dark:bg-gray-950 space-y-4">
          {messages.length === 0 && !loading && (
            <div className="h-full flex flex-col items-center justify-center text-center px-4">
              <div className="bg-green-50 dark:bg-gray-800 text-[#10b981] p-4 rounded-full mb-3">
                <MessageCircle size={32} />
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Ask me anything about your fitness, nutrition, or workout plan!</p>
            </div>
          )}

          {messages.map((msg, index) => (
            <div key={index} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] ${msg.role === 'user' ? 'bg-[#10b981] text-white rounded-2xl rounded-br-sm' : 'bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 border border-gray-100 dark:border-gray-700 rounded-2xl rounded-bl-sm'} p-3 shadow-sm text-sm`}>
                {msg.role === 'user' ? (
                  <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                ) : (
                  <div className="ai-markdown leading-relaxed">
                    <ReactMarkdown
                      components={{
                        a: ({ node, ...props }) => (
                          <a {...props} target="_blank" rel="noopener noreferrer"
                            className="text-[#10b981] underline hover:opacity-80" />
                        ),
                        p: ({ node, ...props }) => <p {...props} className="mb-1.5 last:mb-0" />,
                        ul: ({ node, ...props }) => <ul {...props} className="list-disc pl-4 mb-1.5 space-y-0.5" />,
                        ol: ({ node, ...props }) => <ol {...props} className="list-decimal pl-4 mb-1.5 space-y-0.5" />,
                        strong: ({ node, ...props }) => <strong {...props} className="font-semibold" />,
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                )}
                {msg.role === 'user' ? null : msg.sources && (
                  <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-2 border-t border-gray-100 dark:border-gray-700 pt-1">
                    Source: <span className="italic">{msg.sources}</span>
                  </p>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700 p-4 rounded-2xl rounded-bl-sm shadow-sm max-w-[80%]">
                <div className="flex space-x-1.5 items-center">
                  <span className="w-1.5 h-1.5 bg-[#10b981] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-1.5 h-1.5 bg-[#10b981] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-1.5 h-1.5 bg-[#10b981] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Field */}
        <div className="p-3 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 shrink-0">
          <form onSubmit={handleSend} className="flex items-end space-x-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend(e);
                }
              }}
              placeholder="Type your question..."
              disabled={loading}
              className="flex-1 max-h-32 min-h-[44px] px-4 py-2.5 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#10b981] focus:border-transparent text-sm text-gray-800 dark:text-gray-100 resize-none"
              rows="1"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className={`bg-[#10b981] text-white p-2.5 rounded-full shadow hover:bg-[#059669] transition-colors shrink-0 ${(loading || !input.trim()) ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Send size={18} />
            </button>
          </form>
        </div>
      </div>

      {/* Floating Toggle Button */}
      <button
        onClick={toggleChat}
        className={`bg-[#10b981] hover:bg-[#059669] text-white p-4 rounded-full shadow-lg transition-transform hover:scale-105 active:scale-95 focus:outline-none focus:ring-4 focus:ring-green-400 focus:ring-opacity-50 ${isOpen ? 'rotate-90 scale-0 opacity-0 absolute pointer-events-none' : 'rotate-0 scale-100 opacity-100'}`}
        aria-label="Toggle AI Coach Menu"
      >
        <MessageCircle size={32} />
      </button>
    </div>
  );
};

export default GlobalChatOverlay;
