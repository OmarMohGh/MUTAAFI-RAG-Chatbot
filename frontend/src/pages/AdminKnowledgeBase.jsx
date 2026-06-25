/**
 * =========================================================================
 * AdminKnowledgeBase.jsx — Knowledge Base Admin Panel
 * =========================================================================
 *
 * PURPOSE:
 *   Provides an admin-only form to add new knowledge entries to the
 *   Mutaafi AI Coach's RAG knowledge base.  Each entry consists of a
 *   content summary (converted to embeddings), an optional source title,
 *   and an optional source URL.
 *
 * FEATURE / PAGE:
 *   Admin Knowledge Base — restricted admin tool.
 *
 * BACKEND CONNECTION:
 *   - POST /api/admin/knowledge — Sends the knowledge entry payload
 *     with a JWT Bearer token for admin authorisation.
 *
 * RELATED COMPONENTS:
 *   - App.jsx router — Mounts at '/admin/knowledge'.
 * =========================================================================
 */

// ======================= IMPORTS =======================
import React, { useState, useEffect } from 'react';
import { supabase } from '../supabaseClient';
import { Database, Plus, CheckCircle, AlertCircle } from 'lucide-react';

// ======================= COMPONENT =======================
/**
 * AdminKnowledgeBase — form to add RAG knowledge entries.
 * @returns {JSX.Element}
 */
const AdminKnowledgeBase = () => {

  // ======================= STATE & HOOKS =======================

  // Set the browser tab title on first render
  useEffect(() => {
    document.title = "Admin Knowledge Base | Mutaafi";
  }, []);

  // The main text content that will be vectorised into embeddings
  const [contentSummary, setContentSummary] = useState('');
  // Optional human-readable source title for attribution
  const [sourceTitle, setSourceTitle] = useState('');
  // Optional URL linking back to the original source
  const [sourceUrl, setSourceUrl] = useState('');
  // Whether the form submission is in progress
  const [loading, setLoading] = useState(false);
  // Status banner: { type: 'success'|'error', message: '...' }
  const [status, setStatus] = useState({ type: '', message: '' });

  // ======================= EVENT HANDLERS =======================

  /**
   * Validates the form and POSTs the knowledge entry to the backend.
   * The content_summary is required; source fields are optional.
   *
   * @param {React.FormEvent} e — The form submit event.
   * @returns {Promise<void>}
   * Triggered when the "Add to Knowledge Base" button is clicked.
   */
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!contentSummary) {
      setStatus({ type: 'error', message: 'Content summary is required.' });
      return;
    }

    setLoading(true);
    setStatus({ type: '', message: '' });

    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error('Not authenticated');
      }

      const response = await fetch('http://localhost:5000/api/admin/knowledge', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`
        },
        body: JSON.stringify({
          content_summary: contentSummary,
          source_title: sourceTitle,
          source_url: sourceUrl
        })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to add knowledge');
      }

      setStatus({ type: 'success', message: 'Knowledge entry successfully added to the database!' });
      
      // Reset form
      setContentSummary('');
      setSourceTitle('');
      setSourceUrl('');
      
    } catch (error) {
      setStatus({ type: 'error', message: error.message });
    } finally {
      setLoading(false);
    }
  };

  // ======================= RETURN (JSX) =======================
  return (
    <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl overflow-hidden border border-gray-100 dark:border-gray-700">
        <div className="bg-gradient-to-r from-[#108a6e] to-[#19cba3] p-8 text-white">
          <div className="flex items-center space-x-4">
            <div className="p-3 bg-white/20 rounded-lg backdrop-blur-sm">
              <Database className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Knowledge Base Admin</h1>
              <p className="text-blue-50 mt-2 font-medium">Manage and train the Mutaafi AI Coach with new verified facts.</p>
            </div>
          </div>
        </div>

        <div className="p-8">
          {status.message && (
            <div className={`mb-6 p-4 rounded-xl flex items-center space-x-3 ${status.type === 'success' ? 'bg-[#eafff6] text-[#108a6e] dark:bg-green-900/30 dark:text-[#19cba3]' : 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400'}`}>
              {status.type === 'success' ? <CheckCircle className="w-5 h-5 flex-shrink-0" /> : <AlertCircle className="w-5 h-5 flex-shrink-0" />}
              <p className="font-medium">{status.message}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="content_summary" className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                Content Summary / Fact *
              </label>
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                Provide the exact information you want the AI to know. This will be converted to embeddings.
              </p>
              <textarea
                id="content_summary"
                rows={5}
                className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-[#108a6e] focus:border-transparent transition-colors resize-none"
                placeholder="e.g., Squats primarily target the quadriceps, glutes, and hamstrings..."
                value={contentSummary}
                onChange={(e) => setContentSummary(e.target.value)}
                required
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label htmlFor="source_title" className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Source Title
                </label>
                <input
                  type="text"
                  id="source_title"
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-[#108a6e] focus:border-transparent transition-colors"
                  placeholder="e.g., Exercise Guide: Squats"
                  value={sourceTitle}
                  onChange={(e) => setSourceTitle(e.target.value)}
                />
              </div>

              <div>
                <label htmlFor="source_url" className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Source URL
                </label>
                <input
                  type="url"
                  id="source_url"
                  className="w-full px-4 py-3 rounded-xl border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-[#108a6e] focus:border-transparent transition-colors"
                  placeholder="https://mutaafi.com/guides/..."
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                />
              </div>
            </div>

            <div className="pt-4 flex justify-end">
              <button
                type="submit"
                disabled={loading}
                className="inline-flex items-center space-x-2 bg-[#108a6e] hover:bg-[#0d735c] text-white px-6 py-3 rounded-xl font-bold shadow-md hover:shadow-lg transition-all duration-200 disabled:opacity-70 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <>
                    <Plus className="w-5 h-5" />
                    <span>Add to Knowledge Base</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

// ======================= EXPORT =======================
export default AdminKnowledgeBase;
