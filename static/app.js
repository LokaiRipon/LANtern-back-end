// ---------- GLOBALS ----------
let currentUser = null;
let token = null;
let socket = null;
let currentView = 'mail';
let activeRoom = null;  // for meeting chat

// ---------- DOM REFS ----------
const loginScreen = document.getElementById('login-screen');
const dashboard = document.getElementById('dashboard');
const viewContainer = document.getElementById('view-container');
const userInfoSpan = document.getElementById('user-info');

// ---------- HELPERS ----------
function showDashboard() {
  loginScreen.style.display = 'none';
  dashboard.style.display = 'block';
  userInfoSpan.textContent = currentUser.full_name + ' (' + currentUser.role + ')';
  renderView('mail');
}

function showNotification(msg) {
  // Simple alert for now; can be improved
  alert(msg);
}

// ---------- API CALLS ----------
async function apiFetch(url, opts = {}) {
  opts.headers = opts.headers || {};
  if (token) {
    opts.headers['Authorization'] = 'Bearer ' + token;
  }
  opts.headers['Content-Type'] = 'application/json';
  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Request failed');
  }
  return res.json();
}

// ---------- LOGIN / REGISTER ----------
document.getElementById('login-btn').addEventListener('click', async () => {
  const username = document.getElementById('username').value;
  const password = document.getElementById('password').value;
  try {
    const data = await apiFetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password })
    });
    token = data.access_token;
    currentUser = data.user;
    showDashboard();
    connectWebSocket();
  } catch (e) {
    document.getElementById('login-error').textContent = e.message;
  }
});

document.getElementById('register-toggle').addEventListener('click', (e) => {
  e.preventDefault();
  const form = document.getElementById('register-form');
  form.style.display = form.style.display === 'none' ? 'block' : 'none';
});

document.getElementById('register-btn').addEventListener('click', async () => {
  const username = document.getElementById('reg-username').value;
  const password = document.getElementById('reg-password').value;
  const full_name = document.getElementById('reg-fullname').value;
  const role = document.getElementById('reg-role').value;
  const department = document.getElementById('reg-dept').value || 'General';
  try {
    await apiFetch('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username, password, full_name, role, department })
    });
    alert('Registration successful! Please log in.');
    document.getElementById('register-form').style.display = 'none';
  } catch (e) {
    document.getElementById('register-error').textContent = e.message;
  }
});

// ---------- LOGOUT ----------
document.getElementById('logout-btn').addEventListener('click', async () => {
  try {
    await apiFetch('/api/auth/logout', { method: 'POST' });
  } catch (e) {}
  if (socket) socket.close();
  token = null;
  currentUser = null;
  loginScreen.style.display = 'flex';
  dashboard.style.display = 'none';
});

// ---------- WEBSOCKET ----------
function connectWebSocket() {
  const ws = new WebSocket(`ws://${window.location.host}/ws/${currentUser.id}`);
  ws.onopen = () => console.log('WebSocket connected');
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleWSMessage(msg);
  };
  ws.onclose = () => {
    console.log('WebSocket disconnected, reconnecting...');
    setTimeout(connectWebSocket, 3000);
  };
  socket = ws;
}

function handleWSMessage(msg) {
  switch (msg.type) {
    case 'new_message':
      // If currently viewing inbox, refresh
      if (currentView === 'mail') renderView('mail');
      break;
    case 'public_announcement':
      showNotification('📢 PA: ' + msg.announcement.content);
      if (currentView === 'pa') renderView('pa');
      break;
    case 'meeting_invite':
      showNotification('📅 New meeting invitation: ' + msg.meeting.title);
      break;
    case 'meeting_chat':
      // If in the same room, append message
      if (activeRoom) {
        const chatArea = document.getElementById('meeting-chat-messages');
        if (chatArea) {
          const div = document.createElement('div');
          div.textContent = `[${msg.from}] ${msg.message}`;
          chatArea.appendChild(div);
          chatArea.scrollTop = chatArea.scrollHeight;
        }
      }
      break;
    case 'call_offer':
      handleCallOffer(msg.from, msg.sdp);
      break;
    case 'call_answer':
      handleCallAnswer(msg.from, msg.sdp);
      break;
    case 'ice_candidate':
      handleIceCandidate(msg.from, msg.candidate);
      break;
    case 'end_call':
      endCall();
      break;
    case 'presence':
      // Update user list if on users view
      if (currentView === 'users') renderView('users');
      break;
    default:
      console.log('Unhandled WS message:', msg);
  }
}

// ---------- VIEW RENDERING ----------
function renderView(view) {
  currentView = view;
  // Update sidebar active
  document.querySelectorAll('.sidebar ul li').forEach(li => li.classList.remove('active'));
  document.querySelector(`.sidebar ul li[data-view="${view}"]`)?.classList.add('active');

  switch (view) {
    case 'mail': renderMail(); break;
    case 'pa': renderPA(); break;
    case 'meetings': renderMeetings(); break;
    case 'calls': renderCalls(); break;
    case 'users': renderUsers(); break;
    default: viewContainer.innerHTML = '<h2>Unknown view</h2>';
  }
}

// ---------- MAIL ----------
async function renderMail() {
  const inbox = await apiFetch('/api/mail/inbox');
  const sent = await apiFetch('/api/mail/sent');
  let html = `<h2><i class="fas fa-envelope"></i> Inbox</h2>`;
  if (inbox.length === 0) html += `<p>No messages.</p>`;
  inbox.forEach(m => {
    html += `<div class="card">
      <div class="card-header"><span>From: ${m.sender_id}</span><span>${new Date(m.timestamp).toLocaleString()}</span></div>
      <div class="card-body">${m.content}</div>
    </div>`;
  });
  html += `<h2><i class="fas fa-paper-plane"></i> Compose</h2>
    <div class="card">
      <select id="compose-recipient"><option value="">Select recipient</option></select>
      <textarea id="compose-content" rows="3" placeholder="Message"></textarea>
      <button class="btn btn-primary" id="compose-send">Send</button>
    </div>
    <h2><i class="fas fa-history"></i> Sent</h2>`;
  if (sent.length === 0) html += `<p>No sent messages.</p>`;
  sent.forEach(m => {
    html += `<div class="card">
      <div class="card-header"><span>To: ${m.recipient_id}</span><span>${new Date(m.timestamp).toLocaleString()}</span></div>
      <div class="card-body">${m.content}</div>
    </div>`;
  });
  viewContainer.innerHTML = html;
  // Populate recipient dropdown
  const users = await apiFetch('/api/users');
  const select = document.getElementById('compose-recipient');
  users.forEach(u => {
    if (u.id !== currentUser.id) {
      const opt = document.createElement('option');
      opt.value = u.id;
      opt.textContent = u.full_name + ' (' + u.username + ')';
      select.appendChild(opt);
    }
  });
  document.getElementById('compose-send').addEventListener('click', async () => {
    const recipient = parseInt(select.value);
    const content = document.getElementById('compose-content').value;
    if (!recipient || !content) return alert('Fill all fields');
    await apiFetch('/api/mail', {
      method: 'POST',
      body: JSON.stringify({ recipient_id: recipient, content })
    });
    document.getElementById('compose-content').value = '';
    renderView('mail');
  });
}

// ---------- PUBLIC ADDRESS ----------
async function renderPA() {
  const anns = await apiFetch('/api/public');
  let html = `<h2><i class="fas fa-bullhorn"></i> Public Address</h2>`;
  if (anns.length === 0) html += `<p>No announcements.</p>`;
  anns.forEach(a => {
    html += `<div class="card">
      <div class="card-header"><span>From: ${a.sender_id}</span><span>${new Date(a.timestamp).toLocaleString()}</span></div>
      <div class="card-body">${a.content}</div>
    </div>`;
  });
  // Only CEO/Manager can post
  if (['CEO','Manager'].includes(currentUser.role)) {
    html += `<div class="card">
      <textarea id="pa-content" rows="3" placeholder="Broadcast message..."></textarea>
      <button class="btn btn-primary" id="pa-send">Broadcast</button>
    </div>`;
  }
  viewContainer.innerHTML = html;
  if (document.getElementById('pa-send')) {
    document.getElementById('pa-send').addEventListener('click', async () => {
      const content = document.getElementById('pa-content').value;
      if (!content) return alert('Enter message');
      await apiFetch('/api/public', {
        method: 'POST',
        body: JSON.stringify({ content })
      });
      document.getElementById('pa-content').value = '';
      renderView('pa');
    });
  }
}

// ---------- MEETINGS ----------
async function renderMeetings() {
  const meetings = await apiFetch('/api/meetings');
  let html = `<h2><i class="fas fa-calendar-alt"></i> Meetings</h2>`;
  if (meetings.length === 0) html += `<p>No meetings.</p>`;
  meetings.forEach(m => {
    html += `<div class="meeting-item">
      <div class="meeting-title">${m.title}</div>
      <div class="meeting-time">${new Date(m.start_time).toLocaleString()} ${m.end_time ? '- ' + new Date(m.end_time).toLocaleString() : ''}</div>
      <div>Organizer: ${m.organizer_id} | Room: ${m.room_id}</div>
      <div>Attendees: ${m.attendees.map(u => u.full_name).join(', ') || 'None'}</div>
      <button class="btn btn-primary" data-meeting-id="${m.id}" data-room="${m.room_id}">Join Chat</button>
    </div>`;
  });
  // Schedule new meeting (CEO/Manager only)
  if (['CEO','Manager'].includes(currentUser.role)) {
    html += `<div class="card">
      <h3>Schedule New Meeting</h3>
      <input type="text" id="meeting-title" placeholder="Title">
      <textarea id="meeting-desc" placeholder="Description (optional)"></textarea>
      <label>Start: <input type="datetime-local" id="meeting-start"></label>
      <label>End: <input type="datetime-local" id="meeting-end"></label>
      <div>Select attendees:</div>
      <div id="attendee-checkboxes"></div>
      <button class="btn btn-primary" id="meeting-schedule">Schedule</button>
    </div>`;
  }
  viewContainer.innerHTML = html;

  // Populate attendee checkboxes
  if (document.getElementById('attendee-checkboxes')) {
    const users = await apiFetch('/api/users');
    const container = document.getElementById('attendee-checkboxes');
    users.forEach(u => {
      if (u.id !== currentUser.id) {
        const label = document.createElement('label');
        label.innerHTML = `<input type="checkbox" value="${u.id}"> ${u.full_name} (${u.role})`;
        container.appendChild(label);
        container.appendChild(document.createElement('br'));
      }
    });
  }

  // Schedule button
  if (document.getElementById('meeting-schedule')) {
    document.getElementById('meeting-schedule').addEventListener('click', async () => {
      const title = document.getElementById('meeting-title').value;
      const desc = document.getElementById('meeting-desc').value;
      const start = document.getElementById('meeting-start').value;
      const end = document.getElementById('meeting-end').value;
      const checked = document.querySelectorAll('#attendee-checkboxes input:checked');
      const attendee_ids = Array.from(checked).map(cb => parseInt(cb.value));
      if (!title || !start) return alert('Title and start time required');
      await apiFetch('/api/meetings', {
        method: 'POST',
        body: JSON.stringify({ title, description: desc, start_time: start, end_time: end || null, attendee_ids })
      });
      renderView('meetings');
    });
  }

  // Join chat buttons
  document.querySelectorAll('[data-meeting-id]').forEach(btn => {
    btn.addEventListener('click', function() {
      const roomId = this.dataset.room;
      joinMeetingRoom(roomId);
    });
  });
}

async function joinMeetingRoom(roomId) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: 'join_room', room_id: roomId }));
    activeRoom = roomId;
    // Show chat UI
    viewContainer.innerHTML = `
      <h2><i class="fas fa-comments"></i> Meeting Chat</h2>
      <div id="meeting-chat-messages" style="height:300px; overflow-y:auto; background:#1f2a1b; padding:10px; border-radius:6px;"></div>
      <div class="flex-row">
        <input type="text" id="chat-input" placeholder="Type message...">
        <button class="btn btn-primary" id="chat-send">Send</button>
      </div>
      <button class="btn btn-danger" id="chat-leave">Leave Room</button>
    `;
    document.getElementById('chat-send').addEventListener('click', () => {
      const input = document.getElementById('chat-input');
      const msg = input.value.trim();
      if (!msg) return;
      socket.send(JSON.stringify({ type: 'meeting_chat', room_id: roomId, message: msg }));
      // Append own message
      const chatArea = document.getElementById('meeting-chat-messages');
      const div = document.createElement('div');
      div.textContent = `[You] ${msg}`;
      chatArea.appendChild(div);
      chatArea.scrollTop = chatArea.scrollHeight;
      input.value = '';
    });
    document.getElementById('chat-leave').addEventListener('click', () => {
      socket.send(JSON.stringify({ type: 'leave_room', room_id: roomId }));
      activeRoom = null;
      renderView('meetings');
    });
  } else {
    alert('WebSocket not connected');
  }
}

// ---------- CALLS ----------
let peerConnection = null;
let localStream = null;
let remoteAudio = null;
let callTarget = null;

async function renderCalls() {
  const users = await apiFetch('/api/users');
  let html = `<h2><i class="fas fa-phone"></i> Voice Calls</h2>
    <div class="card">
      <h3>Start a Call</h3>
      <select id="call-target">
        <option value="">Select user</option>`;
  users.forEach(u => {
    if (u.id !== currentUser.id) {
      html += `<option value="${u.id}">${u.full_name} (${u.username})</option>`;
    }
  });
  html += `</select>
      <button class="btn btn-primary" id="call-start">Call</button>
    </div>
    <div id="call-status" class="call-container" style="display:none;">
      <div class="call-status">Call in progress...</div>
      <button class="btn btn-danger" id="call-end">End Call</button>
      <audio id="remote-audio" autoplay></audio>
    </div>`;
  viewContainer.innerHTML = html;
  document.getElementById('call-start').addEventListener('click', () => {
    const target = parseInt(document.getElementById('call-target').value);
    if (!target) return alert('Select a user');
    startCall(target);
  });
  document.getElementById('call-end')?.addEventListener('click', endCall);
}

async function startCall(targetId) {
  callTarget = targetId;
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    peerConnection = new RTCPeerConnection({ iceServers: [] });
    peerConnection.onicecandidate = (event) => {
      if (event.candidate) {
        socket.send(JSON.stringify({
          type: 'ice_candidate',
          target: callTarget,
          candidate: event.candidate
        }));
      }
    };
    peerConnection.ontrack = (event) => {
      const audio = document.getElementById('remote-audio');
      if (audio) {
        audio.srcObject = event.streams[0];
        audio.play();
      }
    };
    localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));
    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    socket.send(JSON.stringify({
      type: 'call_offer',
      target: callTarget,
      sdp: offer
    }));
    document.getElementById('call-status').style.display = 'block';
  } catch (e) {
    alert('Could not start call: ' + e.message);
  }
}

function handleCallOffer(from, sdp) {
  if (confirm(`Incoming call from user ${from}. Accept?`)) {
    callTarget = from;
    // Answer
    (async () => {
      try {
        localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        peerConnection = new RTCPeerConnection({ iceServers: [] });
        peerConnection.onicecandidate = (event) => {
          if (event.candidate) {
            socket.send(JSON.stringify({
              type: 'ice_candidate',
              target: callTarget,
              candidate: event.candidate
            }));
          }
        };
        peerConnection.ontrack = (event) => {
          const audio = document.getElementById('remote-audio');
          if (audio) {
            audio.srcObject = event.streams[0];
            audio.play();
          }
        };
        localStream.getTracks().forEach(track => peerConnection.addTrack(track, localStream));
        await peerConnection.setRemoteDescription(new RTCSessionDescription(sdp));
        const answer = await peerConnection.createAnswer();
        await peerConnection.setLocalDescription(answer);
        socket.send(JSON.stringify({
          type: 'call_answer',
          target: callTarget,
          sdp: answer
        }));
        document.getElementById('call-status').style.display = 'block';
      } catch (e) {
        alert('Call setup failed');
      }
    })();
  } else {
    // reject
    socket.send(JSON.stringify({ type: 'end_call', target: from }));
  }
}

function handleCallAnswer(from, sdp) {
  if (peerConnection) {
    peerConnection.setRemoteDescription(new RTCSessionDescription(sdp));
  }
}

function handleIceCandidate(from, candidate) {
  if (peerConnection) {
    peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
  }
}

function endCall() {
  if (peerConnection) {
    peerConnection.close();
    peerConnection = null;
  }
  if (localStream) {
    localStream.getTracks().forEach(t => t.stop());
    localStream = null;
  }
  if (callTarget) {
    socket.send(JSON.stringify({ type: 'end_call', target: callTarget }));
    callTarget = null;
  }
  document.getElementById('call-status').style.display = 'none';
}

// ---------- USERS ----------
async function renderUsers() {
  const users = await apiFetch('/api/users');
  let html = `<h2><i class="fas fa-users"></i> Users</h2>
    <div class="user-list">`;
  users.forEach(u => {
    const online = u.is_online ? 'online' : '';
    html += `<div class="user-chip ${online}">
      ${u.full_name} <span class="role-badge">${u.role}</span>
      ${u.is_online ? '🟢' : '⚪'}
    </div>`;
  });
  html += `</div>`;
  viewContainer.innerHTML = html;
}

// ---------- SIDEBAR NAVIGATION ----------
document.querySelectorAll('.sidebar ul li').forEach(li => {
  li.addEventListener('click', function() {
    const view = this.dataset.view;
    if (view) renderView(view);
  });
});

// ---------- KEYBOARD SHORTCUT: Enter to login ----------
document.getElementById('password').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') document.getElementById('login-btn').click();
});