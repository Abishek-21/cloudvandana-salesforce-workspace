import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const OBJECTS = ['Account', 'Opportunity', 'Lead', 'Contact', 'Case'];
const DESCRIPTIONS = {
  Account: 'Companies and organisations you work with.',
  Opportunity: 'Deals, stages and the value of your pipeline.',
  Lead: 'People and companies at the start of your sales process.',
  Contact: 'People connected to your customer accounts.',
  Case: 'Customer questions and support requests.',
};
const AUTH_ERRORS = {
  configuration: 'Complete the local Salesforce connection settings before signing in.',
  cancelled: 'Salesforce login was cancelled. You can try again when you are ready.',
  exchange: 'Salesforce could not complete login. Check the External Client App settings and callback URL, then try again.',
};

function Icon({ name, size = 20 }) {
  const paths = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    arrow: <path d="M5 12h14m-6-6 6 6-6 6"/>,
    refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 7a7 7 0 0 1 12-1l2 3M4 15l2 3a7 7 0 0 0 12-1"/></>,
    close: <path d="m6 6 12 12M6 18 18 6"/>,
    eye: <><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>,
    edit: <><path d="m15 4 5 5M4 20l4-1L21 6a2 2 0 0 0-5-5L3 14l-1 6Z"/></>,
    trash: <><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/></>,
    shield: <><path d="m12 2 8 4v6c0 5-8 10-8 10S4 17 4 12V6l8-4Z"/><path d="m8 12 3 3 5-6"/></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v7c0 4 16 4 16 0V5M4 12v7c0 4 16 4 16 0v-7"/></>,
  };
  return <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name] || paths.grid}</svg>;
}

function display(value, field) {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (field.type === 'currency') return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
  if (field.type === 'percent') return `${value}%`;
  return String(value);
}
function recordTitle(record) {
  return record.Name || [record.FirstName, record.LastName].filter(Boolean).join(' ') || record.Subject || record.CaseNumber || record.Id;
}

function App() {
  const [session, setSession] = useState(null);
  const [sessionError, setSessionError] = useState('');
  const [selected, setSelected] = useState('Account');
  const [schema, setSchema] = useState(null);
  const [records, setRecords] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [modal, setModal] = useState(null);
  const [working, setWorking] = useState(false);
  const [revision, setRevision] = useState(0);
  const scroller = useRef(null);
  const sentinel = useRef(null);
  const requestVersion = useRef(0);
  const pendingPage = useRef(false);
  const triggerRef = useRef(null);
  const [authError] = useState(() => {
    const key = new URLSearchParams(window.location.search).get('auth_error');
    if (key) window.history.replaceState(null, '', '/');
    return AUTH_ERRORS[key] || '';
  });

  const request = useCallback(async (url, options = {}) => {
    const response = await fetch(url, {
      ...options,
      credentials: 'same-origin',
      headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.method && options.method !== 'GET' ? { 'X-CSRF-Token': session?.csrfToken || '' } : {}),
        ...options.headers },
    });
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) {
      setSession(current => ({ ...current, authenticated: false }));
      setModal(null);
    }
    if (!response.ok) {
      const detail = typeof data.detail === 'string' ? data.detail : 'Please check your entries and try again.';
      throw new Error(detail);
    }
    return data;
  }, [session?.csrfToken]);

  const loadSession = useCallback(async () => {
    setSessionError('');
    try {
      const response = await fetch('/api/session', { credentials: 'same-origin' });
      if (!response.ok) throw new Error('The server is unavailable. Please try again shortly.');
      setSession(await response.json());
    } catch (err) { setSessionError(err.message); }
  }, []);
  useEffect(() => { loadSession(); }, [loadSession]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 6500);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const current = ++requestVersion.current;
    const controller = new AbortController();
    setSchema(null); setRecords([]); setCursor(null); setError(''); setLoaded(false); setModal(null);
    pendingPage.current = false;
    if (!session?.authenticated) { setLoading(false); return () => controller.abort(); }
    setLoading(true);
    Promise.all([
      request(`/api/objects/${selected}/schema`, { signal: controller.signal }),
      request(`/api/objects/${selected}/records`, { signal: controller.signal }),
    ]).then(([meta, page]) => {
      if (current !== requestVersion.current) return;
      setSchema(meta); setRecords(page.records); setCursor(page.nextCursor); setLoaded(true);
      if (scroller.current) scroller.current.scrollTop = 0;
    }).catch(err => {
      if (err.name !== 'AbortError' && current === requestVersion.current) setError(err.message);
    }).finally(() => { if (current === requestVersion.current) setLoading(false); });
    return () => controller.abort();
  }, [selected, session?.authenticated, revision, request]);

  const nextPage = useCallback(async () => {
    if (!cursor || loading || pendingPage.current || error) return;
    pendingPage.current = true; setLoading(true);
    const current = requestVersion.current;
    try {
      const page = await request(`/api/objects/${selected}/records?after=${encodeURIComponent(cursor)}`);
      if (current !== requestVersion.current) return;
      setRecords(old => [...old, ...page.records.filter(r => !old.some(o => o.Id === r.Id))]);
      setCursor(page.nextCursor);
    } catch (err) { if (current === requestVersion.current) setError(err.message); }
    finally { if (current === requestVersion.current) { pendingPage.current = false; setLoading(false); } }
  }, [cursor, loading, error, request, selected]);
  useEffect(() => {
    if (!sentinel.current || !scroller.current || !loaded) return;
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) nextPage();
    }, { root: scroller.current, rootMargin: '0px 0px 80px 0px' });
    observer.observe(sentinel.current);
    return () => observer.disconnect();
  }, [loaded, nextPage]);

  function openModal(mode, record = null, target = null) {
    triggerRef.current = target || document.activeElement;
    setModal({ mode, record });
  }
  function closeModal() { setModal(null); triggerRef.current?.focus(); }
  async function logout() {
    setWorking(true); setError('');
    try {
      const result = await request('/auth/logout', { method: 'POST' });
      setSession(current => ({ ...current, authenticated: false }));
      setModal(null); setRecords([]); setSchema(null);
      window.location.assign(result.logoutUrl);
    }
    catch (err) { setError(err.message); }
    finally { setWorking(false); }
  }
  async function viewRecord(record, target) {
    setWorking(true); setError('');
    const current = requestVersion.current;
    try {
      const fresh = await request(`/api/objects/${selected}/records/${record.Id}`);
      if (current === requestVersion.current) openModal('view', fresh, target);
    } catch (err) { if (current === requestVersion.current) setError(err.message); }
    finally { setWorking(false); }
  }
  async function save(values) {
    const creating = modal.mode === 'create';
    const id = modal.record?.Id;
    const result = await request(`/api/objects/${selected}/records${creating ? '' : `/${id}`}`, {
      method: creating ? 'POST' : 'PATCH', body: JSON.stringify({ values }),
    });
    // Keep the saved values if the refresh fails.
    let fresh;
    try {
      fresh = await request(`/api/objects/${selected}/records/${creating ? result.id : id}`);
    } catch {
      fresh = { ...modal.record, ...values, Id: creating ? result.id : id };
      setError('The record was saved, but its latest details could not be reloaded. Use Reload records to check them.');
    }
    setRecords(old => creating ? [fresh, ...old] : old.map(r => r.Id === fresh.Id ? fresh : r));
    setToast(`${selected} ${creating ? 'created' : 'updated'} successfully.`);
    closeModal();
  }
  async function removeRecord() {
    await request(`/api/objects/${selected}/records/${modal.record.Id}`, { method: 'DELETE' });
    setRecords(old => old.filter(r => r.Id !== modal.record.Id));
    setToast(`${selected} deleted successfully.`); closeModal();
  }

  const authenticated = session?.authenticated;
  return <div className="app-shell">
    <header className="topbar">
      <a className="brand" href="/" aria-label="Salesforce Workspace home"><span className="brand-mark"><Icon name="grid" size={21}/></span><span>Salesforce <strong>Workspace</strong></span></a>
      <div className="topbar-right"><span className={`connection-pill ${authenticated ? 'connected' : ''}`}><span className="dot"/>{authenticated ? 'Connected' : 'Not connected'}</span>{authenticated && <button className="text-button" onClick={logout} disabled={working} title="Also signs out of this Salesforce org in your browser">Log out</button>}</div>
    </header>
    <main>
      <div className="page-heading"><div><p className="eyebrow">SALESFORCE RECORD MANAGEMENT</p><h1>Your customer workspace.</h1><p className="subtitle">Five objects. One clear view of the work.</p></div><span className="local-label"><Icon name="shield" size={16}/> Salesforce integration</span></div>
      {sessionError ? <div className="error-panel" role="alert"><h2>Could not connect to the server</h2><p>{sessionError}</p><button className="button secondary" onClick={loadSession}>Try again</button></div> : !session ? <div className="loading-panel" role="status"><span className="spinner"/> Opening your workspace…</div> : !authenticated ? <>
        {authError && <div className="banner error" role="alert">{authError}</div>}
        {error && <div className="banner error" role="alert">{error}</div>}
        <section className="login-panel"><div className="login-copy"><span className="feature-icon"><Icon name="database" size={30}/></span><p className="eyebrow">LET’S GET CONNECTED</p><h2>Your Salesforce records,<br/>ready to work with.</h2><p>Sign in to your Developer Org to browse records, make changes and keep your customer information up to date.</p>
          {session.configured ? <a className="button primary" href="/auth/login">Log in to Salesforce <Icon name="arrow" size={18}/></a> : <><button className="button primary" disabled>Log in to Salesforce <Icon name="arrow" size={18}/></button><div className="setup-notice"><strong>Connection setup needed</strong><p>Add your External Client App credentials to the local configuration and restart the server.</p><details><summary>Settings to complete</summary><ul>{session.missing.map(key => <li key={key}>{key}</li>)}</ul></details></div></>}
        </div><div className="login-features"><div className="feature-heading">A focused way to manage your CRM</div>{OBJECTS.map((name, i) => <div className="object-feature" key={name}><span className={`object-icon color-${i}`}>{name.slice(0, 1)}</span><div><strong>{name}</strong><p>{DESCRIPTIONS[name]}</p></div></div>)}<div className="privacy-note"><Icon name="shield" size={18}/><span>You log in directly with Salesforce. Your password is never entered in this app.</span></div></div></section>
        <div className="capabilities"><span>Create and update records</span><span>20 records per page</span><span>Your Salesforce permissions apply</span></div>
      </> : <>
        <section className="workspace" aria-label="Salesforce records">
          <div className="workspace-toolbar"><div className="object-picker"><label htmlFor="object-select">OBJECT</label><select id="object-select" value={selected} onChange={event => setSelected(event.target.value)} disabled={working}>{OBJECTS.map(name => <option key={name}>{name}</option>)}</select></div><div className="toolbar-description"><h2>{schema?.pluralLabel || `${selected} records`}</h2><p>{DESCRIPTIONS[selected]}</p></div><div className="toolbar-actions"><button className="button secondary icon-button" title="Reload records" aria-label="Reload records" onClick={() => setRevision(n => n + 1)} disabled={loading || working}><Icon name="refresh"/></button><button className="button primary" onClick={() => openModal('create')} disabled={!schema?.createable || loading || working}><Icon name="plus" size={18}/> New {selected}</button></div></div>
          <div className="table-meta"><span>{records.length} records loaded{schema && <> <span className="meta-separator">/</span> {schema.fields.length} fields</>}</span><span className="org-name" title={session.org}><span className="dot"/>{session.org}</span></div>
          {error && <div className="banner error" role="alert"><span>{error}</span><button className="text-button" onClick={() => { setError(''); if (!loaded) setRevision(n => n + 1); }}>Try again</button></div>}
          <div className="table-scroller" ref={scroller} tabIndex={0} aria-label={`${selected} records. Scroll to load more.`}>
            {schema && records.length > 0 && <table><thead><tr><th className="row-number">#</th>{schema.fields.map(f => <th key={f.name}>{f.label}</th>)}<th className="actions-cell">Actions</th></tr></thead><tbody>{records.map((record, i) => <tr key={record.Id}><td className="row-number">{i + 1}</td>{schema.fields.map(f => <td key={f.name} title={display(record[f.name], f)} className={f.name === 'Id' || f.type === 'reference' ? 'mono-cell' : ''}>{f.name === 'Name' || f.name === 'Subject' ? <button className="record-link" onClick={event => viewRecord(record, event.currentTarget)} disabled={working}>{display(record[f.name], f)}</button> : display(record[f.name], f)}</td>)}<td className="actions-cell"><div className="row-actions"><button title="View record" aria-label={`View ${recordTitle(record)}`} onClick={event => viewRecord(record, event.currentTarget)} disabled={working}><Icon name="eye" size={17}/></button><button title="Edit record" aria-label={`Edit ${recordTitle(record)}`} onClick={() => openModal('edit', record)} disabled={!schema.updateable || working}><Icon name="edit" size={17}/></button><button className="danger-icon" title="Delete record" aria-label={`Delete ${recordTitle(record)}`} onClick={() => openModal('delete', record)} disabled={!schema.deletable || working}><Icon name="trash" size={17}/></button></div></td></tr>)}</tbody></table>}
            {!loading && loaded && records.length === 0 && <div className="empty-state"><span className="empty-icon"><Icon name="database" size={30}/></span><h3>No {selected.toLowerCase()} records yet</h3><p>Create your first record to get started.</p>{schema?.createable && <button className="button secondary" onClick={() => openModal('create')}><Icon name="plus" size={17}/> New {selected}</button>}</div>}
            {loading && <div className="loading-panel" role="status"><span className="spinner"/> Loading {selected.toLowerCase()} records…</div>}
            <div ref={sentinel} className="page-sentinel"/>
            {loaded && !loading && records.length > 0 && <div className="end-message">{cursor ? <button className="text-button" onClick={nextPage} disabled={!!error}>Load next 20 records</button> : 'You’re up to date. All available records are loaded.'}</div>}
          </div>
        </section>
        <p className="workspace-footnote"><Icon name="shield" size={15}/> Changes are saved directly to your connected Salesforce org.</p>
      </>}
    </main>
    <footer><span>Salesforce Workspace</span><span>Built by Abishek Budhiraja · Associate Software Engineer assignment</span></footer>
    {toast && <div className="toast" role="status">✓ {toast}<button aria-label="Dismiss notification" onClick={() => setToast('')}><Icon name="close" size={17}/></button></div>}
    {modal && schema && <RecordModal key={`${selected}-${modal.mode}-${modal.record?.Id || 'new'}`} modal={modal} schema={schema} close={closeModal} save={save} remove={removeRecord} edit={() => setModal({ ...modal, mode: 'edit' })}/>}
  </div>;
}

function RecordModal({ modal, schema, close, save, remove, edit }) {
  const { mode, record } = modal;
  const dialog = useRef(null);
  const [values, setValues] = useState(() => Object.fromEntries(schema.fields.filter(f => mode === 'create' ? f.createable : f.updateable).map(f => {
    const initial = record?.[f.name] ?? f.default ?? (f.options.find(o => o.default)?.value) ?? (f.type === 'boolean' ? false : '');
    return [f.name, initial];
  })));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    const d = dialog.current;
    d.showModal();
    const cancel = event => { event.preventDefault(); if (!busy) close(); };
    d.addEventListener('cancel', cancel);
    return () => d.removeEventListener('cancel', cancel);
  }, [close, busy]);
  async function submit(event) {
    event.preventDefault();
    // Capture input values before the dialog re-renders.
    const submitted = new FormData(event.currentTarget);
    setBusy(true); setError('');
    try {
      if (mode === 'delete') await remove();
      else {
        const payload = {};
        for (const field of schema.fields) {
          if (!(mode === 'create' ? field.createable : field.updateable)) continue;
          let value = field.type === 'boolean' ? values[field.name]
            : field.type === 'multipicklist' ? submitted.getAll(field.name).join(';')
            : submitted.get(field.name) ?? values[field.name];
          if (value === '') {
            if (mode === 'create') continue;
            value = field.nillable ? null : '';
          } else if (['currency', 'double', 'int', 'percent'].includes(field.type)) {
            value = Number(value);
          }
          if (mode === 'edit' && (value ?? '') === (record[field.name] ?? '')) continue;
          payload[field.name] = value;
        }
        if (!Object.keys(payload).length) { setError('Make a change before saving.'); return; }
        await save(payload);
      }
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  const fields = schema.fields.filter(f => mode === 'create' ? f.createable : f.updateable);
  return <dialog ref={dialog} className={`record-modal ${mode === 'delete' ? 'delete-modal' : ''}`} aria-labelledby="modal-title" onClick={event => { if (event.target === dialog.current && !busy) close(); }}>
    <form onSubmit={submit}><div className="modal-heading"><div><p className="eyebrow">{schema.name.toUpperCase()}</p><h2 id="modal-title">{mode === 'create' ? `New ${schema.name}` : mode === 'edit' ? `Edit ${schema.name}` : mode === 'delete' ? 'Delete this record?' : recordTitle(record)}</h2></div><button type="button" className="icon-button" aria-label="Close dialog" onClick={close} disabled={busy}><Icon name="close"/></button></div>
      <div className="modal-body">
        {error && <div className="banner error" role="alert">{error}</div>}
        {mode === 'delete' ? <><div className="delete-symbol"><Icon name="trash" size={28}/></div><p>You are deleting <strong>{recordTitle(record)}</strong> from Salesforce.</p><p className="muted">This may also affect related data according to your org’s rules. Confirm that this is the intended record.</p><code className="record-id">{record.Id}</code></> : mode === 'view' ? <dl className="detail-grid">{schema.fields.map(f => <div className={f.type === 'textarea' ? 'full-width' : ''} key={f.name}><dt>{f.label}</dt><dd>{display(record[f.name], f)}</dd></div>)}</dl> : <><p className="form-hint">Fields marked <span className="required-mark">*</span> are required. Your Salesforce validation rules also apply.</p><div className="form-grid">{fields.map(f => <Field key={f.name} field={f} value={values[f.name]} change={value => setValues(v => ({ ...v, [f.name]: value }))} disabled={busy}/>)}</div></>}
      </div><div className="modal-footer"><button type="button" className="button secondary" onClick={close} disabled={busy}>{mode === 'view' ? 'Close' : 'Cancel'}</button>{mode === 'view' ? schema.updateable && <button type="button" className="button primary" onClick={edit}><Icon name="edit" size={16}/> Edit record</button> : <button className={`button ${mode === 'delete' ? 'danger' : 'primary'}`} type="submit" disabled={busy}>{busy ? <><span className="spinner"/> Saving…</> : mode === 'delete' ? 'Delete record' : mode === 'create' ? 'Create record' : 'Save changes'}</button>}</div></form>
  </dialog>;
}

function Field({ field: f, value, change, disabled }) {
  const attrs = { id: `field-${f.name}`, name: f.name, disabled, required: f.required,
    value: value ?? '', onChange: e => change(e.target.value), maxLength: f.length > 0 ? f.length : undefined };
  let control;
  if (f.type === 'boolean') control = <label className="checkbox-control"><input type="checkbox" disabled={disabled} checked={!!value} onChange={e => change(e.target.checked)}/> {f.label}</label>;
  else if (f.type === 'picklist') control = <select {...attrs}><option value="">Select {f.label.toLowerCase()}</option>{value && !f.options.some(o => o.value === value) && <option value={value}>{value}</option>}{f.options.map(o => <option value={o.value} key={o.value}>{o.label}</option>)}</select>;
  else if (f.type === 'textarea') control = <textarea {...attrs} rows={4}/>;
  else if (f.type === 'multipicklist') control = <select id={attrs.id} name={attrs.name} multiple disabled={disabled} required={f.required} value={String(value || '').split(';').filter(Boolean)} onChange={e => change(Array.from(e.target.selectedOptions, o => o.value).join(';'))}>{f.options.map(o => <option value={o.value} key={o.value}>{o.label}</option>)}</select>;
  else {
    const numeric = ['currency', 'double', 'int', 'percent'].includes(f.type);
    const type = numeric ? 'number' : f.type === 'date' ? 'date' : f.type === 'datetime' ? 'datetime-local' : f.type === 'email' ? 'email' : f.type === 'phone' ? 'tel' : 'text';
    if (type === 'date' || type === 'datetime-local') {
      const { value: initialValue, ...dateAttrs } = attrs;
      control = <input {...dateAttrs} type={type} defaultValue={initialValue}/>;
    } else control = <input {...attrs} type={type} step={numeric ? f.type === 'int' ? 1 : 'any' : undefined} placeholder={f.type === 'reference' ? 'Salesforce record ID' : ''}/>;
  }
  return <div className={`form-field ${f.type === 'textarea' ? 'full-width' : ''}`}>{f.type !== 'boolean' && <label htmlFor={attrs.id}>{f.label}{f.required && <span className="required-mark"> *</span>}</label>}{control}{f.type === 'reference' && <small>{f.required ? 'Required' : 'Optional'} {f.referenceTo.join(' / ')} record ID (15 or 18 characters).</small>}</div>;
}

createRoot(document.getElementById('root')).render(<App/>);
