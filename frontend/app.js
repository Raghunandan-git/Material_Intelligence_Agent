// app.js
const API_URL = 'http://localhost:8000/api';

const chatInput = document.getElementById('chat-input-field');
const sendBtn = document.getElementById('chat-send-btn');
const chatHistory = document.getElementById('chat-history');
const chatList = document.getElementById('chat-list');
const newChatBtn = document.getElementById('new-chat-btn');

let currentSessionId = null;

marked.setOptions({
    breaks: true,
    gfm: true
});

async function init() {
    await loadSessions();
    if (!currentSessionId) {
        const sessions = await fetchSessions();
        if (sessions.length > 0) {
            loadSession(sessions[0]._id);
        } else {
            createNewChat();
        }
    }
}

async function fetchSessions() {
    try {
        const response = await fetch(`${API_URL}/sessions`);
        if (response.ok) {
            return await response.json();
        }
    } catch (error) {
        console.error("Failed to fetch sessions:", error);
    }
    return [];
}

async function loadSessions() {
    const sessions = await fetchSessions();
    chatList.innerHTML = '';
    sessions.forEach(session => {
        const div = document.createElement('div');
        div.className = `chat-session-item ${session._id === currentSessionId ? 'active' : ''}`;
        div.textContent = session.title || "New Chat";
        div.onclick = () => loadSession(session._id);
        chatList.appendChild(div);
    });
    return sessions;
}

async function createNewChat() {
    try {
        const response = await fetch(`${API_URL}/sessions`, { method: 'POST' });
        if (response.ok) {
            const session = await response.json();
            await loadSessions(); 
            loadSession(session._id);
        }
    } catch (error) {
        console.error("Failed to create session:", error);
    }
}

async function loadSession(sessionId) {
    if (currentSessionId === sessionId) return;

    currentSessionId = sessionId;

    document.querySelectorAll('.chat-session-item').forEach(el => {
        el.classList.remove('active');
    });
    await loadSessions();

    chatHistory.innerHTML = '';

    try {
        const response = await fetch(`${API_URL}/sessions/${sessionId}`);
        if (response.ok) {
            const session = await response.json();

            if (session.history && session.history.length > 0) {
                session.history.forEach(msg => {
                    addMessageToUI(msg.content, msg.role === 'user' ? 'user' : 'bot');
                });
            } else {
                const welcomeDiv = document.createElement('div');
                welcomeDiv.classList.add('message', 'bot');
                welcomeDiv.textContent = "Hello! I am your Material Intelligence Agent. Describe your application, requirements, or constraints, and I will help you find the perfect material.";
                chatHistory.appendChild(welcomeDiv);
            }
            scrollToBottom();
        }
    } catch (error) {
        console.error("Failed to load session:", error);
    }
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;

    if (!currentSessionId) {
        await createNewChat();
    }

    addMessageToUI(text, 'user');
    chatInput.value = '';

    const loadingId = addLoadingIndicator();

    try {
        const response = await fetch(`${API_URL}/chat/${currentSessionId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }) 
        });

        removeMessage(loadingId);

        if (response.ok) {
            const data = await response.json();
            addMessageToUI(data.response, 'bot');

            loadSessions();
        } else {
            addMessageToUI("Error: Could not connect to the agent.", 'bot');
        }

    } catch (error) {
        removeMessage(loadingId);
        addMessageToUI("Error connecting to server.", 'bot');
        console.error(error);
    }
}

function addMessageToUI(text, sender) {
    const div = document.createElement('div');
    div.classList.add('message', sender);

    if (sender === 'bot') {
        div.innerHTML = marked.parse(text);
    } else {
        div.textContent = text;
    }

    chatHistory.appendChild(div);
    scrollToBottom();
}

function addLoadingIndicator() {
    const id = 'loading-' + Date.now();
    const div = document.createElement('div');
    div.id = id;
    div.classList.add('message', 'bot');
    div.innerHTML = '<em>Thinking...</em>';
    chatHistory.appendChild(div);
    scrollToBottom();
    return id;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function scrollToBottom() {
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

sendBtn.addEventListener('click', sendMessage);
newChatBtn.addEventListener('click', createNewChat);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

window.onload = () => {
    chatInput.focus();
    init();
};
