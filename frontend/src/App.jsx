import { useEffect, useState } from 'react';

const initialMessages = [
  {
    id: 1,
    role: 'assistant',
    content: 'Welcome to Enterprise AI Mentor. Sign in, upload a PDF, and ask grounded questions about your company documents.',
  },
];

function App() {
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState('');
  const [employee, setEmployee] = useState(null);
  const [signupData, setSignupData] = useState({ name: '', email: '', department: '', role: '' });
  const [loginEmail, setLoginEmail] = useState('');
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState('');

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/documents');
      const data = await response.json();
      setDocuments(data);
    } catch (error) {
      setStatus('Unable to load document list.');
    }
  };

  const signup = async (event) => {
    event.preventDefault();
    try {
      const response = await fetch('http://localhost:8000/api/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(signupData),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Signup failed');
      setEmployee(data.employee);
      setStatus(`Signed up as ${data.employee.name}`);
    } catch (error) {
      setStatus(error.message);
    }
  };

  const login = async (event) => {
    event.preventDefault();
    try {
      const response = await fetch('http://localhost:8000/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Login failed');
      setEmployee(data.employee);
      setStatus(`Welcome back, ${data.employee.name}`);
    } catch (error) {
      setStatus(error.message);
    }
  };

  const uploadFile = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    setUploading(true);
    setStatus('Uploading document...');

    try {
      const response = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Upload failed');
      await fetchDocuments();
      setStatus(`Uploaded ${data.document.filename}`);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setUploading(false);
    }
  };

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMessage = { id: Date.now(), role: 'user', content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: input }),
      });

      const data = await response.json();
      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: data.answer || 'No answer returned.',
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 2,
          role: 'assistant',
          content: 'Unable to reach the backend right now.',
        },
      ]);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 p-6 text-slate-800">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="rounded-2xl bg-slate-900 p-6 text-white shadow-lg">
          <h1 className="text-2xl font-semibold">Enterprise AI Mentor MVP</h1>
          <p className="mt-2 text-sm text-slate-300">Internal knowledge assistant for employees</p>
        </header>

        {status ? <div className="rounded-xl bg-white p-3 text-sm text-slate-600 shadow-sm">{status}</div> : null}

        <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold">Employee Chat</h2>
            <div className="flex h-[420px] flex-col gap-3 overflow-y-auto rounded-xl bg-slate-50 p-3">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`max-w-[80%] rounded-2xl px-4 py-2 ${message.role === 'user' ? 'ml-auto bg-slate-900 text-white' : 'bg-white text-slate-700 shadow-sm'}`}
                >
                  {message.content}
                </div>
              ))}
            </div>
            <div className="mt-3 flex gap-2">
              <input
                className="flex-1 rounded-xl border border-slate-300 px-3 py-2 outline-none"
                placeholder="Ask about HR, policies, or training"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && sendMessage()}
              />
              <button
                className="rounded-xl bg-slate-900 px-4 py-2 text-white"
                onClick={sendMessage}
              >
                Send
              </button>
            </div>
          </section>

          <aside className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-lg font-semibold">Employee Access</h2>
              <p className="mt-2 text-sm text-slate-600">Sign up or log in to use the assistant.</p>
              <form className="mt-3 space-y-2" onSubmit={signup}>
                <input className="w-full rounded-xl border px-3 py-2" placeholder="Name" value={signupData.name} onChange={(event) => setSignupData({ ...signupData, name: event.target.value })} />
                <input className="w-full rounded-xl border px-3 py-2" placeholder="Email" value={signupData.email} onChange={(event) => setSignupData({ ...signupData, email: event.target.value })} />
                <input className="w-full rounded-xl border px-3 py-2" placeholder="Department" value={signupData.department} onChange={(event) => setSignupData({ ...signupData, department: event.target.value })} />
                <input className="w-full rounded-xl border px-3 py-2" placeholder="Role" value={signupData.role} onChange={(event) => setSignupData({ ...signupData, role: event.target.value })} />
                <button className="w-full rounded-xl bg-slate-900 px-3 py-2 text-white" type="submit">Sign up</button>
              </form>

              <form className="mt-4 space-y-2" onSubmit={login}>
                <input className="w-full rounded-xl border px-3 py-2" placeholder="Existing email" value={loginEmail} onChange={(event) => setLoginEmail(event.target.value)} />
                <button className="w-full rounded-xl border border-slate-300 px-3 py-2" type="submit">Log in</button>
              </form>

              {employee ? <p className="mt-3 text-sm text-slate-600">Signed in as {employee.name} ({employee.department})</p> : null}
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-lg font-semibold">Admin Panel</h2>
              <p className="mt-2 text-sm text-slate-600">Upload PDFs to build the knowledge base.</p>
              <input className="mt-3 w-full rounded-xl border border-dashed border-slate-300 p-3 text-sm" type="file" accept="application/pdf" onChange={uploadFile} />
              {uploading ? <p className="mt-2 text-sm text-slate-500">Uploading...</p> : null}
              <div className="mt-3">
                <h3 className="text-sm font-semibold">Uploaded documents</h3>
                <ul className="mt-2 space-y-2 text-sm text-slate-600">
                  {documents.length === 0 ? <li>No documents yet.</li> : documents.map((document) => <li key={document.filename} className="rounded-lg bg-slate-50 p-2">{document.filename}</li>)}
                </ul>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

export default App;
