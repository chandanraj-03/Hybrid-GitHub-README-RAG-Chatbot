/**
 * README RAG Chatbot - Embeddable Vanilla JavaScript Component
 * 
 * Exposes window.initializeChatbot(options) for seamless integration
 * into any web page or documentation portal.
 */

(function (global) {
    'use strict';

    class ReadmeChatbot {
        constructor(options = {}) {
            this.projectId = options.projectId || '';
            this.apiUrl = (options.apiUrl || 'http://localhost:8000').replace(/\/+$/, '');
            this.theme = options.theme || 'dark';
            this.autoOpen = !!options.autoOpen;
            this.containerId = options.containerId || 'readme-chatbot-root';
            
            this.isOpen = false;
            this.isLoading = false;
            this.messages = [];
            this.projectInfo = null;

            this.initDOM();
            this.bindEvents();

            if (this.projectId) {
                this.fetchProjectDetails();
            }

            if (this.autoOpen) {
                this.open();
            }
        }

        /**
         * Builds the widget HTML structure and mounts it to the DOM.
         */
        initDOM() {
            let root = document.getElementById(this.containerId);
            if (!root) {
                root = document.createElement('div');
                root.id = this.containerId;
                document.body.appendChild(root);
            }

            root.innerHTML = `
                <!-- Floating Action Button -->
                <button class="readme-chat-fab" id="readmeChatFab" aria-label="Open README AI Chat">
                    <span class="fab-icon-open">🤖</span>
                    <span class="fab-icon-close">✕</span>
                </button>

                <!-- Chatbot Window -->
                <div class="readme-chat-window" id="readmeChatWindow" role="dialog" aria-modal="true">
                    <div class="chat-window-header">
                        <div class="chat-header-info">
                            <div class="chat-bot-avatar">🤖</div>
                            <div class="chat-title-group">
                                <h4 id="chatHeaderTitle">README Assistant</h4>
                                <div class="chat-subtitle">
                                    <span class="dot-online"></span>
                                    <span id="chatHeaderSubtitle">Project Grounded AI</span>
                                </div>
                            </div>
                        </div>
                        <div class="chat-header-actions">
                            <button class="chat-header-btn" id="btnChatClear" title="Clear Chat History">🗑️</button>
                            <button class="chat-header-btn" id="btnChatClose" title="Close Chat">✕</button>
                        </div>
                    </div>

                    <div class="chat-messages-container" id="chatMessagesContainer">
                        <!-- Welcome message -->
                        <div class="chat-message bot">
                            <div class="message-bubble">
                                <p>👋 <strong>Hello!</strong> I am your documentation assistant.</p>
                                <p>Ask me anything about this repository's <code>README.md</code> (installation, features, architecture, setup, etc.).</p>
                            </div>
                        </div>
                    </div>

                    <div class="chat-input-container">
                        <form class="chat-input-form" id="chatInputForm">
                            <textarea 
                                class="chat-input-textarea" 
                                id="chatInputTextarea" 
                                placeholder="Ask a question about this README..." 
                                rows="1"
                                maxlength="500"
                                required
                            ></textarea>
                            <button type="submit" class="chat-send-btn" id="chatSendBtn" aria-label="Send Query">
                                ➤
                            </button>
                        </form>
                    </div>
                </div>
            `;

            // Cache element references
            this.fab = document.getElementById('readmeChatFab');
            this.window = document.getElementById('readmeChatWindow');
            this.messagesContainer = document.getElementById('chatMessagesContainer');
            this.inputForm = document.getElementById('chatInputForm');
            this.textarea = document.getElementById('chatInputTextarea');
            this.sendBtn = document.getElementById('chatSendBtn');
            this.btnClose = document.getElementById('btnChatClose');
            this.btnClear = document.getElementById('btnChatClear');
            this.headerTitle = document.getElementById('chatHeaderTitle');
            this.headerSubtitle = document.getElementById('chatHeaderSubtitle');
        }

        /**
         * Binds user event listeners (click, enter-to-send, escape).
         */
        bindEvents() {
            this.fab.addEventListener('click', () => this.toggle());
            this.btnClose.addEventListener('click', () => this.close());
            this.btnClear.addEventListener('click', () => this.clearChat());

            // Auto-resize textarea and submit on Enter (without Shift)
            this.textarea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (!this.isLoading && this.textarea.value.trim()) {
                        this.inputForm.dispatchEvent(new Event('submit'));
                    }
                }
            });

            this.textarea.addEventListener('input', () => {
                this.textarea.style.height = 'auto';
                this.textarea.style.height = `${Math.min(this.textarea.scrollHeight, 100)}px`;
            });

            this.inputForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const text = this.textarea.value.trim();
                if (text && !this.isLoading) {
                    this.sendMessage(text);
                }
            });

            // Close on Escape key
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && this.isOpen) {
                    this.close();
                }
            });
        }

        toggle() {
            if (this.isOpen) {
                this.close();
            } else {
                this.open();
            }
        }

        open() {
            this.isOpen = true;
            this.fab.classList.add('open');
            this.window.classList.add('active');
            setTimeout(() => this.textarea.focus(), 150);
        }

        close() {
            this.isOpen = false;
            this.fab.classList.remove('open');
            this.window.classList.remove('active');
        }

        clearChat() {
            this.messagesContainer.innerHTML = `
                <div class="chat-message bot">
                    <div class="message-bubble">
                        <p>🧹 <em>Chat history cleared.</em></p>
                        <p>Ask a question regarding the repository README!</p>
                    </div>
                </div>
            `;
            this.messages = [];
        }

        updateConfig(newConfig = {}) {
            if (newConfig.projectId) this.projectId = newConfig.projectId;
            if (newConfig.apiUrl) this.apiUrl = newConfig.apiUrl.replace(/\/+$/, '');
            this.fetchProjectDetails();
        }

        /**
         * Fetches project metadata from the backend API.
         */
        async fetchProjectDetails() {
            if (!this.projectId || this.projectId === 'demo-project-id') {
                this.headerTitle.innerText = 'README Assistant';
                this.headerSubtitle.innerText = 'Demo Mode (No UUID)';
                return;
            }

            try {
                const resp = await fetch(`${this.apiUrl}/api/projects/${this.projectId}`);
                if (resp.ok) {
                    const data = await resp.json();
                    this.projectInfo = data;
                    this.headerTitle.innerText = `${data.owner}/${data.repo_name}`;
                    this.headerSubtitle.innerText = `${data.chunk_count} README Chunks`;

                    // Update parent demo preview if elements exist
                    const repoBadge = document.getElementById('repoNameBadge');
                    const chunksBadge = document.getElementById('chunksBadge');
                    const modelBadge = document.getElementById('modelBadge');
                    if (repoBadge) repoBadge.innerText = `📦 Repository: ${data.owner}/${data.repo_name}`;
                    if (chunksBadge) chunksBadge.innerText = `📄 Chunks: ${data.chunk_count}`;
                    if (modelBadge) modelBadge.innerText = `🧠 Model: ${data.embedding_model}`;
                } else {
                    this.headerSubtitle.innerText = 'Project ID not found';
                }
            } catch (err) {
                console.warn('Could not fetch project details:', err);
                this.headerSubtitle.innerText = 'API Offline';
            }
        }

        /**
         * Sends a query to the /api/chat endpoint.
         */
        async sendMessage(question) {
            // Add user message to UI
            this.appendMessage('user', question);
            this.textarea.value = '';
            this.textarea.style.height = 'auto';

            this.setLoading(true);

            try {
                const payload = {
                    project_id: this.projectId,
                    question: question
                };

                const resp = await fetch(`${this.apiUrl}/api/chat`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                if (!resp.ok) {
                    const errData = await resp.json().catch(() => ({}));
                    throw new Error(errData.detail || `Server responded with status ${resp.status}`);
                }

                const data = await resp.json();
                this.appendMessage('bot', data.answer, data.sources || []);
            } catch (err) {
                console.error('Chat error:', err);
                this.appendMessage('bot', `⚠️ **Error:** ${err.message || 'Failed to connect to the chatbot server.'}`);
            } finally {
                this.setLoading(false);
            }
        }

        setLoading(isLoading) {
            this.isLoading = isLoading;
            this.sendBtn.disabled = isLoading;
            this.textarea.disabled = isLoading;

            const existingIndicator = document.getElementById('readmeChatTypingIndicator');
            if (isLoading) {
                if (!existingIndicator) {
                    const indicator = document.createElement('div');
                    indicator.id = 'readmeChatTypingIndicator';
                    indicator.className = 'chat-message bot';
                    indicator.innerHTML = `
                        <div class="typing-indicator">
                            <span class="typing-dot"></span>
                            <span class="typing-dot"></span>
                            <span class="typing-dot"></span>
                        </div>
                    `;
                    this.messagesContainer.appendChild(indicator);
                    this.scrollToBottom();
                }
            } else {
                if (existingIndicator) {
                    existingIndicator.remove();
                }
                this.textarea.focus();
            }
        }

        /**
         * Appends a message bubble with optional sources and markdown parsing.
         */
        appendMessage(sender, text, sources = []) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `chat-message ${sender}`;

            let htmlContent = sender === 'bot' ? this.parseMarkdown(text) : this.escapeHtml(text);

            let sourcesHtml = '';
            if (sources && sources.length > 0) {
                const sourceItems = sources.map(s => {
                    const scorePct = Math.round(s.score * 100);
                    return `
                        <div class="source-item-box">
                            <div class="source-item-header">
                                <span class="source-item-path">📌 ${this.escapeHtml(s.section_path || s.section)}</span>
                                <span class="source-item-score">${scorePct}% match</span>
                            </div>
                            <div class="source-item-content">${this.escapeHtml(s.content)}</div>
                        </div>
                    `;
                }).join('');

                sourcesHtml = `
                    <div class="sources-card" id="sourcesCard_${Date.now()}">
                        <button type="button" class="sources-toggle" onclick="this.parentElement.classList.toggle('expanded')">
                            <div class="sources-toggle-left">
                                <span>📚 Sources from README</span>
                                <span>(${sources.length})</span>
                            </div>
                            <span class="arrow-icon">▼</span>
                        </button>
                        <div class="sources-list">
                            ${sourceItems}
                        </div>
                    </div>
                `;
            }

            msgDiv.innerHTML = `
                <div class="message-bubble">
                    ${htmlContent}
                    ${sourcesHtml}
                </div>
            `;

            this.messagesContainer.appendChild(msgDiv);
            this.scrollToBottom();
        }

        scrollToBottom() {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }

        escapeHtml(str) {
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        /**
         * Lightweight Markdown Parser for chat formatting.
         */
        parseMarkdown(text) {
            if (!text) return '';

            let parsed = this.escapeHtml(text);

            // Fenced code blocks with copy action
            parsed = parsed.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
                return `<pre><code>${code.trim()}</code></pre>`;
            });

            // Inline code
            parsed = parsed.replace(/`([^`]+)`/g, '<code>$1</code>');

            // Links [text](url)
            parsed = parsed.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" style="color: #818cf8; text-decoration: underline;">$1</a>');

            // Bold
            parsed = parsed.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

            // Italic
            parsed = parsed.replace(/\*([^*]+)\*/g, '<em>$1</em>');

            // Paragraphs and newlines
            const paragraphs = parsed.split(/\n\n+/);
            return paragraphs.map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`).join('');
        }
    }

    // Global Initialization Export
    global.initializeChatbot = function (options) {
        return new ReadmeChatbot(options);
    };

})(window);
