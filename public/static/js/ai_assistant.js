/**
 * Haatify AI Fashion Assistant.
 * State, API communication, and DOM rendering are kept separate.
 */
(function () {
    'use strict';

    const STORAGE_KEY = 'haatify_ai_conversation';
    const CHAT_ENDPOINT = '/api/ai-assistant/chat/';
    const FALLBACK_IMAGE = '/static/images/logos/title_logo.png';

    function escapeHtml(str) {
        return String(str || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function formatMarkdownText(rawText) {
        if (!rawText) return '';
        let text = escapeHtml(String(rawText));

        // Convert [Label](url) -> <a href="url" class="ai-msg-link">Label</a>
        text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function (match, label, url) {
            const cleanUrl = url.trim();
            const safeUrl = (cleanUrl.startsWith('/') || cleanUrl.startsWith('http://') || cleanUrl.startsWith('https://')) ? cleanUrl : '#';
            return `<a href="${safeUrl}" class="ai-msg-link">${label}</a>`;
        });

        // Convert **bold** -> <strong>bold</strong>
        text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Convert *italic* -> <em>italic</em>
        text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Convert list bullets (- item)
        text = text.replace(/(?:^|\n)-\s+([^\n]+)/g, '<br>&bull; $1');

        // Convert newlines -> <br>
        text = text.replace(/\n/g, '<br>');

        // Clean redundant leading <br> if any
        if (text.startsWith('<br>')) text = text.slice(4);

        return text;
    }

    class ConversationState {
        constructor(storage) {
            this.storage = storage;
            this.conversationId = this.read();
        }

        read() {
            try {
                return this.storage.getItem(STORAGE_KEY);
            } catch (error) {
                return null;
            }
        }

        save(conversationId) {
            if (!conversationId) return;
            this.conversationId = conversationId;
            try {
                this.storage.setItem(STORAGE_KEY, conversationId);
            } catch (error) {
                // The current page can continue if browser storage is unavailable.
            }
        }

        clear() {
            this.conversationId = null;
            try {
                this.storage.removeItem(STORAGE_KEY);
            } catch (error) {
                // Nothing else is required if browser storage is unavailable.
            }
        }
    }

    class ChatApiError extends Error {
        constructor(message, status, payload) {
            super(message);
            this.name = 'ChatApiError';
            this.status = status;
            this.payload = payload;
        }
    }

    class ChatApi {
        constructor(endpoint, csrfTokenProvider) {
            this.endpoint = endpoint;
            this.csrfTokenProvider = csrfTokenProvider;
        }

        async send(message, conversationId) {
            const payload = { message: message };
            if (conversationId) payload.conversation_id = conversationId;

            const headers = { 'Content-Type': 'application/json' };
            const csrfToken = this.csrfTokenProvider();
            if (csrfToken) headers['X-CSRFToken'] = csrfToken;

            const response = await window.fetch(this.endpoint, {
                method: 'POST',
                credentials: 'same-origin',
                headers: headers,
                body: JSON.stringify(payload)
            });

            let data;
            try {
                data = await response.json();
            } catch (error) {
                throw new ChatApiError(
                    'The assistant returned an unreadable response.',
                    response.status,
                    {}
                );
            }

            if (!response.ok) {
                throw new ChatApiError(
                    data.error || 'An error occurred. Please try again.',
                    response.status,
                    data
                );
            }
            return data;
        }
    }

    class ChatUI {
        constructor(elements) {
            this.elements = elements;
        }

        toggle() {
            if (this.isOpen()) {
                this.close();
            } else {
                this.open();
            }
        }

        isOpen() {
            return this.elements.chatWindow.classList.contains('is-open');
        }

        open() {
            this.elements.chatWindow.classList.add('is-open');
            this.elements.toggleButton.classList.add('is-open');
            if (typeof this.elements.toggleButton.setAttribute === 'function') {
                this.elements.toggleButton.setAttribute('aria-expanded', 'true');
            }
            setTimeout(() => this.elements.input.focus(), 300);
            this.scrollToBottom();
        }

        close() {
            this.elements.chatWindow.classList.remove('is-open');
            this.elements.toggleButton.classList.remove('is-open');
            if (typeof this.elements.toggleButton.setAttribute === 'function') {
                this.elements.toggleButton.setAttribute('aria-expanded', 'false');
            }
            this.elements.toggleButton.focus();
        }

        scrollToBottom() {
            const messages = this.elements.messages;
            messages.scrollTop = messages.scrollHeight;
        }

        setLoading(isLoading) {
            this.elements.input.disabled = isLoading;
            this.elements.sendButton.disabled = isLoading;
            this.elements.typing.style.display = isLoading ? 'flex' : 'none';
            if (!isLoading) setTimeout(() => this.elements.input.focus(), 10);
            this.scrollToBottom();
        }

        renderMessage(text, role, isError) {
            const message = document.createElement('div');
            message.className = `ai-msg ai-msg-${role === 'user' ? 'user' : 'bot'}`;
            if (isError) message.classList.add('ai-error-msg');
            if (role === 'user' || isError) {
                message.appendChild(document.createTextNode(String(text || '')));
            } else {
                message.innerHTML = formatMarkdownText(text);
            }
            this.elements.messages.insertBefore(message, this.elements.typing);
            this.scrollToBottom();
        }

        createProductCard(product, conversationId) {
            const card = document.createElement('a');
            const targetUrl = product.url || '';
            card.href = targetUrl || '#';
            card.className = 'ai-product-card';
            if (targetUrl) {
                card.setAttribute('href', targetUrl);
            }
            card.addEventListener('click', (event) => {
                window.dispatchEvent(new window.CustomEvent('AI_PRODUCT_CLICK', {
                    detail: {
                        product_id: product.id,
                        conversation_id: conversationId,
                        product_url: targetUrl
                    }
                }));
                if (!targetUrl) {
                    event.preventDefault();
                }
            });

            const image = document.createElement('img');
            image.className = 'ai-product-card-img';
            image.src = product.image || FALLBACK_IMAGE;
            image.alt = product.name || 'Haatify product';
            image.addEventListener('error', () => {
                if (image.src !== FALLBACK_IMAGE) image.src = FALLBACK_IMAGE;
            });

            const body = document.createElement('div');
            body.className = 'ai-product-card-body';

            const name = document.createElement('h5');
            name.className = 'ai-product-card-name';
            name.textContent = product.name || 'Product';
            name.title = product.name || 'Product';

            const category = document.createElement('p');
            category.className = 'ai-product-card-category';
            category.textContent = product.category || 'Apparel';

            const price = document.createElement('div');
            price.className = 'ai-product-card-price';
            const hasPrice = product.price !== null && product.price !== undefined && product.price !== '';
            price.textContent = hasPrice ? `BDT ${product.price}` : 'Price unlisted';

            body.appendChild(name);
            body.appendChild(category);
            body.appendChild(price);
            card.appendChild(image);
            card.appendChild(body);
            return card;
        }

        renderProducts(products, conversationId, onChipClick) {
            if (!Array.isArray(products) || products.length === 0) return;

            const classifyGender = (p) => {
                const meta = p.metadata || {};
                const g = String(meta.category_type || meta.gender || '').trim().toLowerCase();
                if (g.includes('women') || g === 'female' || g === 'w') return 'women';
                if (g.includes('men') || g === 'male' || g === 'm') return 'men';
                return 'other';
            };

            const menProducts = [];
            const womenProducts = [];
            const otherProducts = [];

            products.forEach((p) => {
                const g = classifyGender(p);
                if (g === 'men') menProducts.push(p);
                else if (g === 'women') womenProducts.push(p);
                else otherProducts.push(p);
            });

            // If we have both Men's and Women's products, divide into distinct visual collections
            if (menProducts.length > 0 && womenProducts.length > 0) {
                const wrapper = document.createElement('div');
                wrapper.className = 'ai-divided-collection';

                // --- Men's Collection ---
                const menHeader = document.createElement('div');
                menHeader.className = 'ai-collection-header';
                menHeader.innerHTML = '<span class="ai-collection-badge ai-badge-men">👔 Men\'s Collection</span>';
                wrapper.appendChild(menHeader);

                const menRow = document.createElement('div');
                menRow.className = 'ai-products-row';
                menProducts.forEach((p) => menRow.appendChild(this.createProductCard(p, conversationId)));
                wrapper.appendChild(menRow);

                // --- Women's Collection ---
                const womenHeader = document.createElement('div');
                womenHeader.className = 'ai-collection-header';
                womenHeader.innerHTML = '<span class="ai-collection-badge ai-badge-women">👗 Women\'s Collection</span>';
                wrapper.appendChild(womenHeader);

                const womenRow = document.createElement('div');
                womenRow.className = 'ai-products-row';
                womenProducts.forEach((p) => womenRow.appendChild(this.createProductCard(p, conversationId)));
                wrapper.appendChild(womenRow);

                // Any additional items
                if (otherProducts.length > 0) {
                    const otherRow = document.createElement('div');
                    otherRow.className = 'ai-products-row';
                    otherProducts.forEach((p) => otherRow.appendChild(this.createProductCard(p, conversationId)));
                    wrapper.appendChild(otherRow);
                }

                // --- Quick Filter Suggestion Chips ---
                const chipsRow = document.createElement('div');
                chipsRow.className = 'ai-chips-wrapper';

                const chipTitle = document.createElement('span');
                chipTitle.className = 'ai-chips-label';
                chipTitle.textContent = 'Filter collection:';
                chipsRow.appendChild(chipTitle);

                const menChip = document.createElement('button');
                menChip.type = 'button';
                menChip.className = 'ai-filter-chip';
                menChip.textContent = '👔 Men Only';
                menChip.addEventListener('click', () => {
                    if (typeof onChipClick === 'function') onChipClick('Show me only men\'s items');
                });
                chipsRow.appendChild(menChip);

                const womenChip = document.createElement('button');
                womenChip.type = 'button';
                womenChip.className = 'ai-filter-chip';
                womenChip.textContent = '👗 Women Only';
                womenChip.addEventListener('click', () => {
                    if (typeof onChipClick === 'function') onChipClick('Show me only women\'s items');
                });
                chipsRow.appendChild(womenChip);

                wrapper.appendChild(chipsRow);

                this.elements.messages.insertBefore(wrapper, this.elements.typing);
            } else {
                const row = document.createElement('div');
                row.className = 'ai-products-row';
                products.forEach((product) => {
                    row.appendChild(this.createProductCard(product, conversationId));
                });
                this.elements.messages.insertBefore(row, this.elements.typing);
            }

            this.scrollToBottom();
        }
    }

    function getCsrfToken() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput) return csrfInput.value;

        const cookies = document.cookie ? document.cookie.split(';') : [];
        for (let index = 0; index < cookies.length; index += 1) {
            const cookie = cookies[index].trim();
            if (cookie.startsWith('csrftoken=')) {
                return decodeURIComponent(cookie.slice('csrftoken='.length));
            }
        }
        return null;
    }

    function collectElements() {
        return {
            toggleButton: document.getElementById('ai-chat-toggle'),
            chatWindow: document.getElementById('ai-chat-window'),
            closeButton: document.getElementById('ai-chat-close'),
            messages: document.getElementById('ai-chat-messages'),
            form: document.getElementById('ai-chat-form'),
            input: document.getElementById('ai-chat-input'),
            sendButton: document.getElementById('ai-chat-send'),
            typing: document.getElementById('ai-typing-indicator')
        };
    }

    function hasRequiredElements(elements) {
        return Boolean(
            elements.toggleButton && elements.chatWindow && elements.messages &&
            elements.form && elements.input && elements.sendButton && elements.typing
        );
    }

    function isExpiredConversation(error, conversationId) {
        return Boolean(
            conversationId && error instanceof ChatApiError && error.status === 404 &&
            error.payload && error.payload.error === 'Conversation not found.'
        );
    }

    function initializeAssistant() {
        const elements = collectElements();
        if (!hasRequiredElements(elements)) return;

        const state = new ConversationState(window.localStorage);
        const api = new ChatApi(CHAT_ENDPOINT, getCsrfToken);
        const ui = new ChatUI(elements);
        let isProcessing = false;

        elements.toggleButton.addEventListener('click', () => ui.toggle());
        if (elements.closeButton) {
            elements.closeButton.addEventListener('click', () => ui.toggle());
        }
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape' && ui.isOpen()) ui.close();
        });

        async function handleSendMessage(rawText) {
            if (isProcessing) return;

            const message = String(rawText || '').trim();
            if (!message) return;

            isProcessing = true;
            ui.renderMessage(message, 'user', false);
            elements.input.value = '';
            ui.setLoading(true);

            try {
                let data;
                try {
                    data = await api.send(message, state.conversationId);
                } catch (error) {
                    if (!isExpiredConversation(error, state.conversationId)) throw error;
                    state.clear();
                    data = await api.send(message, null);
                }

                state.save(data.conversation_id);
                ui.renderMessage(data.answer || 'I could not create an answer.', 'bot', false);
                ui.renderProducts(data.products, state.conversationId, (chipText) => {
                    handleSendMessage(chipText);
                });
            } catch (error) {
                console.error('AI Chat Error:', error);
                const messageText = error instanceof ChatApiError
                    ? error.message
                    : 'Failed to connect to the assistant. Please check your connection.';
                ui.renderMessage(messageText, 'bot', true);
            } finally {
                isProcessing = false;
                ui.setLoading(false);
            }
        }

        elements.form.addEventListener('submit', async (event) => {
            event.preventDefault();
            await handleSendMessage(elements.input.value);
        });
    }

    document.addEventListener('DOMContentLoaded', initializeAssistant);
}());
