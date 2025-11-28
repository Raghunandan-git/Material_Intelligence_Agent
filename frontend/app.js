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

const downloadBtn = document.getElementById('download-report-btn');
const visualizeBtn = document.getElementById('visualize-btn');
const modal = document.getElementById('visualization-modal');
const closeModal = document.querySelector('.close-modal');
const chartsContainer = document.getElementById('charts-container');

sendBtn.addEventListener('click', sendMessage);
newChatBtn.addEventListener('click', createNewChat);
downloadBtn.addEventListener('click', downloadReport);
visualizeBtn.addEventListener('click', showVisualizations);
closeModal.addEventListener('click', () => modal.style.display = "none");
window.addEventListener('click', (e) => {
    if (e.target == modal) modal.style.display = "none";
});

async function showVisualizations() {
    if (!currentSessionId) {
        alert("Please start a chat session first.");
        return;
    }

    modal.style.display = "block";
    chartsContainer.innerHTML = '<p>Loading charts...</p>';

    const chartTypes = ['tensile', 'density', 'radar'];
    chartsContainer.innerHTML = '';

    for (const type of chartTypes) {
        try {
            const response = await fetch(`${API_URL}/charts/${type}/${currentSessionId}`);
            if (response.ok) {
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);

                const div = document.createElement('div');
                div.className = 'chart-item';
                const img = document.createElement('img');
                img.src = url;
                div.appendChild(img);
                chartsContainer.appendChild(div);
            }
        } catch (e) {
            console.error(`Failed to load ${type} chart`, e);
        }
    }

    if (chartsContainer.children.length === 0) {
        chartsContainer.innerHTML = '<p>No charts available. Try discussing specific materials first.</p>';
    }
}

async function downloadReport() {
    if (!currentSessionId) {
        alert("Please start a chat session first.");
        return;
    }

    const originalText = downloadBtn.innerHTML;
    downloadBtn.innerHTML = 'Generating...';
    downloadBtn.disabled = true;

    try {
        const response = await fetch(`${API_URL}/generate-report/${currentSessionId}`);

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Material_Report_${currentSessionId}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            a.remove();
        } else {
            alert("Failed to generate report. Please try again.");
        }
    } catch (error) {
        console.error("Error downloading report:", error);
        alert("Error downloading report.");
    } finally {
        downloadBtn.innerHTML = originalText;
        downloadBtn.disabled = false;
    }
}
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

window.onload = () => {
    chatInput.focus();
    init();
};
