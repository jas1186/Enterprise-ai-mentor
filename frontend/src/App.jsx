import { useEffect, useState } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const starterMessage = { id: 'welcome', role: 'assistant', data: { message: 'Welcome to the mentor desk. Bring your approach first; I will help you reason through the next step.', questions: ['What engineering problem are you working on today?'], sources: [], compliance: [] } };

function App() {
  const [employee, setEmployee] = useState(() => JSON.parse(localStorage.getItem('mentor_employee') || 'null'));
  const [token, setToken] = useState(() => localStorage.getItem('mentor_token'));
  const [authMode, setAuthMode] = useState('login');
  const [auth, setAuth] = useState({ name: '', email: '', password: '', department: 'Engineering', role: 'Employee' });
  const [messages, setMessages] = useState([starterMessage]);
  const [input, setInput] = useState('');
  const [hintLevel, setHintLevel] = useState(1);
  const [progress, setProgress] = useState({ skills: [], recommendations: [] });
  const [documents, setDocuments] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [upload, setUpload] = useState({ clearance: 1, category: 'general', department: 'Engineering' });
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);

  const request = async (path, options = {}) => {
    const headers = { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(token ? { Authorization: `Bearer ${token}` } : {}) };
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'The mentor service returned an error.');
    return data;
  };

  const loadWorkspace = async () => {
    try {
      const [nextProgress, nextDocuments] = await Promise.all([request('/api/mentor/progress'), request('/api/documents')]);
      setProgress(nextProgress);
      setDocuments(nextDocuments);
      if (employee?.is_admin) setAnalytics(await request('/api/admin/analytics'));
    } catch (error) { setStatus(error.message); }
  };

  useEffect(() => { if (token) loadWorkspace(); }, [token]);

  const authenticate = async (event) => {
    event.preventDefault();
    setBusy(true);
    try {
      const path = authMode === 'login' ? '/api/login' : '/api/signup';
      const body = authMode === 'login' ? { email: auth.email, password: auth.password } : auth;
      const data = await request(path, { method: 'POST', body: JSON.stringify(body) });
      setEmployee(data.employee); setToken(data.access_token);
      localStorage.setItem('mentor_employee', JSON.stringify(data.employee));
      localStorage.setItem('mentor_token', data.access_token);
      setStatus('');
    } catch (error) { setStatus(error.message); } finally { setBusy(false); }
  };

  const logout = () => {
    localStorage.removeItem('mentor_token'); localStorage.removeItem('mentor_employee');
    setToken(null); setEmployee(null); setMessages([starterMessage]);
  };

  const sendMessage = async () => {
    if (!input.trim() || busy) return;
    const question = input.trim();
    setMessages((current) => [...current, { id: Date.now(), role: 'user', data: { message: question } }]);
    setInput(''); setBusy(true);
    try {
      const data = await request('/api/mentor/chat', { method: 'POST', body: JSON.stringify({ question, hint_level: hintLevel }) });
      setMessages((current) => [...current, { id: Date.now() + 1, role: 'assistant', data }]);
      setHintLevel(Math.min(5, hintLevel + 1)); await loadWorkspace();
    } catch (error) { setStatus(error.message); } finally { setBusy(false); }
  };

  const uploadDocument = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file); form.append('required_clearance', String(upload.clearance));
    form.append('category', upload.category); form.append('department', upload.department);
    setBusy(true); setStatus('Indexing document...');
    try { await request('/api/admin/documents', { method: 'POST', body: form }); await loadWorkspace(); setStatus('Document indexed for authorized readers.'); }
    catch (error) { setStatus(error.message); } finally { setBusy(false); event.target.value = ''; }
  };

  if (!employee || !token) return <AuthScreen authMode={authMode} setAuthMode={setAuthMode} auth={auth} setAuth={setAuth} authenticate={authenticate} busy={busy} status={status} />;
  return <Dashboard employee={employee} logout={logout} status={status} messages={messages} input={input} setInput={setInput} sendMessage={sendMessage} busy={busy} hintLevel={hintLevel} setHintLevel={setHintLevel} progress={progress} documents={documents} analytics={analytics} upload={upload} setUpload={setUpload} uploadDocument={uploadDocument} />;
}

function AuthScreen({ authMode, setAuthMode, auth, setAuth, authenticate, busy, status }) {
  return <main className="auth-shell"><section className="auth-brand"><p className="eyebrow">NOVATECH / CAPABILITY SYSTEM</p><h1>Enterprise<br /><em>AI Mentor</em></h1><p className="lead">A senior-engineer style learning desk that makes reasoning visible before it makes answers available.</p><div className="principle"><span>01</span><strong>Think first.</strong><small>Progressive guidance for real engineering judgment.</small></div><div className="principle"><span>02</span><strong>Access responsibly.</strong><small>Every source is filtered by clearance before retrieval.</small></div></section><section className="auth-panel"><div className="panel-kicker">{authMode === 'login' ? 'RETURNING EMPLOYEE' : 'NEW EMPLOYEE'}</div><h2>{authMode === 'login' ? 'Open your mentor desk' : 'Create your learning profile'}</h2><form onSubmit={authenticate} className="form-stack">{authMode === 'signup' && <input required placeholder="Full name" value={auth.name} onChange={(event) => setAuth({ ...auth, name: event.target.value })} />}<input required type="email" placeholder="Work email" value={auth.email} onChange={(event) => setAuth({ ...auth, email: event.target.value })} /><input required minLength="8" type="password" placeholder="Password (8+ characters)" value={auth.password} onChange={(event) => setAuth({ ...auth, password: event.target.value })} />{authMode === 'signup' && <><input required placeholder="Department" value={auth.department} onChange={(event) => setAuth({ ...auth, department: event.target.value })} /><input required placeholder="Role" value={auth.role} onChange={(event) => setAuth({ ...auth, role: event.target.value })} /></>}<button className="primary-button" disabled={busy}>{busy ? 'Connecting...' : authMode === 'login' ? 'Enter mentor desk' : 'Create profile'}</button></form>{status && <p className="error-text">{status}</p>}<button className="text-button" onClick={() => setAuthMode(authMode === 'login' ? 'signup' : 'login')}>{authMode === 'login' ? 'Need a profile? Sign up' : 'Already registered? Log in'}</button></section></main>;
}

function Dashboard({ employee, logout, status, messages, input, setInput, sendMessage, busy, hintLevel, setHintLevel, progress, documents, analytics, upload, setUpload, uploadDocument }) {
  return <main className="app-shell"><header className="topbar"><div><p className="eyebrow">NOVATECH / CAPABILITY SYSTEM</p><h1>Mentor desk <span>·</span> {employee.department}</h1></div><div className="identity"><div><strong>{employee.name}</strong><small>{employee.role} · clearance {employee.clearance_level}</small></div><button className="quiet-button" onClick={logout}>Log out</button></div></header>{status && <div className="status-bar">{status}</div>}<div className="workspace-grid"><section className="mentor-panel"><div className="section-heading"><div><p className="panel-kicker">LIVE COACHING</p><h2>Reasoning room</h2></div><div className="hint-control"><span>GUIDANCE</span><strong>{hintLevel}/5</strong><input type="range" min="1" max="5" value={hintLevel} onChange={(event) => setHintLevel(Number(event.target.value))} /></div></div><div className="messages">{messages.map((item) => <article key={item.id} className={item.role === 'user' ? 'message user-message' : 'message'}><span className="message-label">{item.role === 'user' ? 'YOU' : 'MENTOR'}</span><p>{item.data.message}</p>{item.data.questions?.length > 0 && <div className="questions">{item.data.questions.map((question) => <div key={question}>↳ {question}</div>)}</div>}{item.data.compliance?.length > 0 && <div className="compliance"><strong>COMPLIANCE FLAG · {item.data.compliance[0].severity.toUpperCase()}</strong><p>{item.data.compliance[0].guidance}</p></div>}{item.data.sources?.length > 0 && <div className="source-list">Sources: {item.data.sources.map((source) => <span key={source.id}>{source.filename}</span>)}</div>}{item.data.challenge && <div className="recommendation"><span>FOLLOW-UP CHALLENGE</span><strong>{item.data.challenge}</strong></div>}</article>)}</div><div className="composer"><textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); } }} placeholder="Bring a problem, an attempt, or a design decision..." /><button className="primary-button" onClick={sendMessage} disabled={busy}>Ask mentor ↗</button></div></section><aside className="side-column"><SkillPanel progress={progress} /><LibraryPanel employee={employee} documents={documents} upload={upload} setUpload={setUpload} uploadDocument={uploadDocument} busy={busy} />{employee.is_admin && <AdminPanel analytics={analytics} />}</aside></div></main>;
}

function SkillPanel({ progress }) {
  return <section className="side-section"><div className="section-heading"><div><p className="panel-kicker">SKILL SIGNAL</p><h2>Your profile</h2></div><span className="live-dot">LIVE</span></div>{progress.skills.length === 0 ? <p className="muted">Your first session will create a skill signal.</p> : progress.skills.map((skill) => <div className="skill-row" key={skill.skill}><div><span>{skill.skill}</span><strong>{skill.score}%</strong></div><div className="progress-track"><i style={{ width: `${skill.score}%` }} /></div></div>)}{progress.recommendations.length > 0 && <div className="recommendation"><span>NEXT PRACTICE</span><strong>{progress.recommendations[0].recommendation}</strong></div>}</section>;
}

function LibraryPanel({ employee, documents, upload, setUpload, uploadDocument, busy }) {
  return <section className="side-section"><div className="section-heading"><div><p className="panel-kicker">AUTHORIZED LIBRARY</p><h2>Knowledge sources</h2></div></div>{documents.length === 0 ? <p className="muted">No authorized sources available yet.</p> : documents.map((document) => <div className="document-row" key={document.id}><span className="file-mark">PDF</span><div><strong>{document.filename}</strong><small>Clearance {document.required_clearance} · {document.category}{document.department ? ` · ${document.department}` : ''}</small></div></div>)}{employee.is_admin && <div className="admin-upload"><div className="form-row"><select value={upload.clearance} onChange={(event) => setUpload({ ...upload, clearance: Number(event.target.value) })}><option value="1">Clearance 1</option><option value="2">Clearance 2</option><option value="3">Clearance 3</option><option value="4">Clearance 4</option><option value="5">Clearance 5</option></select><input value={upload.category} onChange={(event) => setUpload({ ...upload, category: event.target.value })} placeholder="Category" /></div><input value={upload.department} onChange={(event) => setUpload({ ...upload, department: event.target.value })} placeholder="Department" /><label className="upload-button">+ Index a PDF<input disabled={busy} type="file" accept="application/pdf" onChange={uploadDocument} /></label></div>}</section>;
}

function AdminPanel({ analytics }) {
  return <section className="side-section"><div className="section-heading"><div><p className="panel-kicker">ADMIN VIEW</p><h2>Learning analytics</h2></div></div>{!analytics ? <p className="muted">Analytics unavailable.</p> : <><div className="analytics-grid"><strong>{analytics.employee_count}<small>employees</small></strong><strong>{analytics.interaction_count}<small>sessions</small></strong><strong>{analytics.average_hint_level}<small>avg hint</small></strong></div><p className="panel-kicker analytics-label">DIFFICULT TOPICS</p>{Object.entries(analytics.topics).sort(([, first], [, second]) => second - first).slice(0, 4).map(([topic, count]) => <div className="analytics-row" key={topic}><span>{topic}</span><strong>{count}</strong></div>)}</>}</section>;
}

export default App;
