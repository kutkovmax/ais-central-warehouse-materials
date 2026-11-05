import { useEffect, useMemo, useState } from "react";

const API_ROOT = import.meta.env.VITE_API_ROOT || "http://127.0.0.1:8765";
const API = `${API_ROOT}/api/v1`;

async function request(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || `Ошибка запроса: ${response.status}`);
  }
  return body;
}

function Field({ label, value, onChange, type = "text", placeholder, min, step }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        min={min}
        step={step}
      />
    </label>
  );
}

function Panel({ title, subtitle, children, action }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Button({ children, kind = "primary", ...props }) {
  return (
    <button className={`button button-${kind}`} {...props}>
      {children}
    </button>
  );
}

function App() {
  const [tab, setTab] = useState("dashboard");
  const [health, setHealth] = useState("Проверка…");
  const [stock, setStock] = useState([]);
  const [message, setMessage] = useState(null);

  const notify = (type, text) => {
    setMessage({ type, text });
    window.setTimeout(() => setMessage(null), 5000);
  };

  const checkHealth = async () => {
    try {
      await fetch(`${API_ROOT}/health`).then(async (response) => {
        if (!response.ok) throw new Error("API недоступен");
        return response.json();
      });
      setHealth("Система в сети");
    } catch (error) {
      setHealth("Нет соединения");
      notify("error", error.message);
    }
  };

  const loadStock = async () => {
    try {
      setStock(await request("/stock"));
    } catch (error) {
      notify("error", error.message);
    }
  };

  useEffect(() => {
    checkHealth();
    loadStock();
  }, []);

  const available = useMemo(
    () => stock.reduce((sum, row) => sum + Number(row.available_quantity || 0), 0),
    [stock],
  );

  const tabs = [
    ["dashboard", "Обзор"],
    ["reference", "Справочники"],
    ["receipts", "Приёмка и ОТК"],
    ["stock", "Остатки"],
    ["requests", "Требования М-11"],
  ];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">СМ</div>
          <div>
            <strong>Склад-МехПром</strong>
            <span>Центральный склад</span>
          </div>
        </div>
        <nav className="nav">
          {tabs.map(([id, label]) => (
            <button
              className={`nav-item ${tab === id ? "active" : ""}`}
              key={id}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="dot dot-green" />
          <div>
            <small>Состояние API</small>
            <strong>{health}</strong>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <p className="eyebrow">АИС центрального склада</p>
            <h1>{tabs.find(([id]) => id === tab)?.[1]}</h1>
          </div>
          <div className="topbar-actions">
            <a href={`${API_ROOT}/docs`} target="_blank" rel="noreferrer" className="api-link">
              OpenAPI
            </a>
            <Button kind="ghost" onClick={checkHealth}>Проверить связь</Button>
          </div>
        </header>

        {message && <div className={`toast toast-${message.type}`}>{message.text}</div>}

        {tab === "dashboard" && (
          <Dashboard health={health} stock={stock} available={available} onRefresh={loadStock} />
        )}
        {tab === "reference" && <Reference notify={notify} />}
        {tab === "receipts" && <Receipts notify={notify} />}
        {tab === "stock" && <Stock stock={stock} onRefresh={loadStock} />}
        {tab === "requests" && <Requests notify={notify} />}
      </main>
    </div>
  );
}

function Dashboard({ health, stock, available, onRefresh }) {
  const accepted = stock.filter((row) => row.qc_status === "ACCEPTED").length;
  const quarantined = stock.filter((row) => row.qc_status === "UNDER_CONTROL").length;
  const rejected = stock.filter((row) => row.qc_status === "REJECTED_QUARANTINE").length;

  return (
    <>
      <div className="hero-card">
        <div>
          <span className="hero-kicker">Оперативная панель</span>
          <h2>Материалы под контролем — от рампы до цеха</h2>
          <p>Приёмка, карантин ОТК, адресное хранение и резервирование М-11 в одном контуре.</p>
        </div>
        <div className="hero-symbol">▦</div>
      </div>

      <div className="stats-grid">
        <div className="stat-card"><span>Строк остатков</span><strong>{stock.length}</strong><small>актуальные ячейки</small></div>
        <div className="stat-card"><span>Доступно</span><strong>{available.toFixed(3)}</strong><small>без учёта резерва</small></div>
        <div className="stat-card"><span>Годные партии</span><strong>{accepted}</strong><small>доступны к выдаче</small></div>
        <div className="stat-card"><span>Карантин / брак</span><strong>{quarantined} / {rejected}</strong><small>операции ОТК</small></div>
      </div>

      <Panel title="Контур склада" subtitle={`API: ${health}`} action={<Button kind="ghost" onClick={onRefresh}>Обновить остатки</Button>}>
        <div className="flow-strip">
          <div><b>01</b><span>Поставка</span><small>ТТН / УПД</small></div>
          <i>→</i>
          <div><b>02</b><span>Зона Q</span><small>контроль ОТК</small></div>
          <i>→</i>
          <div><b>03</b><span>Хранение</span><small>адресная ячейка</small></div>
          <i>→</i>
          <div><b>04</b><span>Цех</span><small>М-11 / FIFO</small></div>
        </div>
      </Panel>
    </>
  );
}

function Reference({ notify }) {
  const [material, setMaterial] = useState({ code: "", name: "", unit: "шт", category: "OTHER" });
  const [supplier, setSupplier] = useState({ inn: "", name: "" });
  const [zone, setZone] = useState({ code: "", name: "", zone_type: "STORAGE" });
  const [cell, setCell] = useState({ address_code: "", zone_id: "", rack_number: 1, section_number: 1, tier_number: 1, position_number: 1, max_weight_kg: 1000, max_volume_m3: 10 });

  const submit = async (path, data, reset) => {
    try {
      await request(path, { method: "POST", body: JSON.stringify(data) });
      notify("success", "Запись создана");
      reset();
    } catch (error) {
      notify("error", error.message);
    }
  };

  return (
    <div className="two-column">
      <Panel title="Материал" subtitle="Номенклатурный справочник">
        <form onSubmit={(event) => { event.preventDefault(); submit("/materials", material, () => setMaterial({ code: "", name: "", unit: "шт", category: "OTHER" })); }}>
          <Field label="Артикул" value={material.code} onChange={(v) => setMaterial({ ...material, code: v })} placeholder="ПОДШ-001" />
          <Field label="Наименование" value={material.name} onChange={(v) => setMaterial({ ...material, name: v })} placeholder="Подшипник" />
          <div className="form-row"><Field label="Ед. изм." value={material.unit} onChange={(v) => setMaterial({ ...material, unit: v })} /><Field label="Категория" value={material.category} onChange={(v) => setMaterial({ ...material, category: v })} /></div>
          <Button type="submit">Создать материал</Button>
        </form>
      </Panel>

      <Panel title="Поставщик" subtitle="Контрагенты поставок">
        <form onSubmit={(event) => { event.preventDefault(); submit("/suppliers", supplier, () => setSupplier({ inn: "", name: "" })); }}>
          <Field label="ИНН" value={supplier.inn} onChange={(v) => setSupplier({ ...supplier, inn: v })} placeholder="7700000000" />
          <Field label="Наименование" value={supplier.name} onChange={(v) => setSupplier({ ...supplier, name: v })} placeholder="АО Поставщик" />
          <Button type="submit">Создать поставщика</Button>
        </form>
      </Panel>

      <Panel title="Зона склада" subtitle="A, B, C, Q, EXP">
        <form onSubmit={(event) => { event.preventDefault(); submit("/zones", zone, () => setZone({ code: "", name: "", zone_type: "STORAGE" })); }}>
          <div className="form-row"><Field label="Код" value={zone.code} onChange={(v) => setZone({ ...zone, code: v })} placeholder="Q" /><Field label="Тип" value={zone.zone_type} onChange={(v) => setZone({ ...zone, zone_type: v })} placeholder="RECEIVING_QUARANTINE" /></div>
          <Field label="Название" value={zone.name} onChange={(v) => setZone({ ...zone, name: v })} placeholder="Карантин" />
          <Button type="submit">Создать зону</Button>
        </form>
      </Panel>

      <Panel title="Адресная ячейка" subtitle="Пример: B-04-12-3-02">
        <form onSubmit={(event) => { event.preventDefault(); const data = { ...cell, zone_id: Number(cell.zone_id), rack_number: Number(cell.rack_number), section_number: Number(cell.section_number), tier_number: Number(cell.tier_number), position_number: Number(cell.position_number), max_weight_kg: Number(cell.max_weight_kg), max_volume_m3: Number(cell.max_volume_m3) }; submit("/storage-cells", data, () => setCell({ ...cell, address_code: "", zone_id: "" })); }}>
          <div className="form-row"><Field label="Адрес" value={cell.address_code} onChange={(v) => setCell({ ...cell, address_code: v })} placeholder="Q-01-01-1-01" /><Field label="ID зоны" type="number" value={cell.zone_id} onChange={(v) => setCell({ ...cell, zone_id: v })} /></div>
          <div className="form-row"><Field label="Ряд" type="number" value={cell.rack_number} onChange={(v) => setCell({ ...cell, rack_number: v })} /><Field label="Секция" type="number" value={cell.section_number} onChange={(v) => setCell({ ...cell, section_number: v })} /><Field label="Ярус" type="number" value={cell.tier_number} onChange={(v) => setCell({ ...cell, tier_number: v })} /></div>
          <div className="form-row"><Field label="Лоток" type="number" value={cell.position_number} onChange={(v) => setCell({ ...cell, position_number: v })} /><Field label="Вес, кг" type="number" value={cell.max_weight_kg} onChange={(v) => setCell({ ...cell, max_weight_kg: v })} /><Field label="Объём, м³" type="number" value={cell.max_volume_m3} onChange={(v) => setCell({ ...cell, max_volume_m3: v })} /></div>
          <Button type="submit">Создать ячейку</Button>
        </form>
      </Panel>
    </div>
  );
}

function Receipts({ notify }) {
  const [receipt, setReceipt] = useState({ document_number: "", supplier_id: "", sku_id: "", batch_number: "", quantity: "", quarantine_cell_id: "" });
  const [qc, setQc] = useState({ batch_id: "", protocol_number: "", certificate_number: "", verdict: "PASSED", rejected_cell_id: "" });
  const submitReceipt = async (event) => {
    event.preventDefault();
    try {
      const result = await request("/receipts", { method: "POST", body: JSON.stringify({ document_number: receipt.document_number, supplier_id: Number(receipt.supplier_id), lines: [{ sku_id: Number(receipt.sku_id), batch_number: receipt.batch_number, quantity: Number(receipt.quantity), quarantine_cell_id: Number(receipt.quarantine_cell_id) }] }) });
      notify("success", `Приход создан. Партия: ${result.batches?.[0]?.id ?? "готова к ОТК"}`);
    } catch (error) { notify("error", error.message); }
  };
  const submitQc = async (event) => {
    event.preventDefault();
    try {
      await request("/qc/inspect", { method: "POST", body: JSON.stringify({ ...qc, batch_id: Number(qc.batch_id), rejected_cell_id: qc.rejected_cell_id ? Number(qc.rejected_cell_id) : null }) });
      notify("success", qc.verdict === "PASSED" ? "Партия допущена к размещению" : "Партия переведена в изолятор брака");
    } catch (error) { notify("error", error.message); }
  };
  return (
    <div className="two-column">
      <Panel title="Новая приёмка" subtitle="Партия поступает в зону Q со статусом UNDER_CONTROL">
        <form onSubmit={submitReceipt}>
          <Field label="Номер М-4" value={receipt.document_number} onChange={(v) => setReceipt({ ...receipt, document_number: v })} placeholder="М4-2026-001" />
          <div className="form-row"><Field label="ID поставщика" type="number" value={receipt.supplier_id} onChange={(v) => setReceipt({ ...receipt, supplier_id: v })} /><Field label="ID материала" type="number" value={receipt.sku_id} onChange={(v) => setReceipt({ ...receipt, sku_id: v })} /></div>
          <div className="form-row"><Field label="Номер партии" value={receipt.batch_number} onChange={(v) => setReceipt({ ...receipt, batch_number: v })} /><Field label="Количество" type="number" step="0.001" value={receipt.quantity} onChange={(v) => setReceipt({ ...receipt, quantity: v })} /></div>
          <Field label="ID карантинной ячейки" type="number" value={receipt.quarantine_cell_id} onChange={(v) => setReceipt({ ...receipt, quarantine_cell_id: v })} />
          <Button type="submit">Зарегистрировать приёмку</Button>
        </form>
      </Panel>
      <Panel title="Решение ОТК" subtitle="ACCEPTED или REJECTED_QUARANTINE">
        <form onSubmit={submitQc}>
          <Field label="ID партии" type="number" value={qc.batch_id} onChange={(v) => setQc({ ...qc, batch_id: v })} />
          <div className="form-row"><Field label="Номер протокола" value={qc.protocol_number} onChange={(v) => setQc({ ...qc, protocol_number: v })} placeholder="ПК-2026-001" /><Field label="Сертификат" value={qc.certificate_number} onChange={(v) => setQc({ ...qc, certificate_number: v })} /></div>
          <label className="field"><span>Вердикт</span><select value={qc.verdict} onChange={(event) => setQc({ ...qc, verdict: event.target.value })}><option value="PASSED">Годен</option><option value="FAILED">Брак</option></select></label>
          {qc.verdict === "FAILED" && <Field label="ID ячейки изолятора (необязательно)" type="number" value={qc.rejected_cell_id} onChange={(v) => setQc({ ...qc, rejected_cell_id: v })} />}
          <Button type="submit" kind={qc.verdict === "FAILED" ? "danger" : "primary"}>Зафиксировать решение</Button>
        </form>
      </Panel>
    </div>
  );
}

function Stock({ stock, onRefresh }) {
  return (
    <Panel title="Остатки по ячейкам" subtitle="Физическое количество, резерв и доступный остаток" action={<Button kind="ghost" onClick={onRefresh}>Обновить</Button>}>
      {stock.length === 0 ? <div className="empty-state">Остатков пока нет. Создайте материал, зону, ячейку и приёмку.</div> : <div className="table-wrap"><table><thead><tr><th>Партия</th><th>Адрес</th><th>Статус ОТК</th><th>Физический остаток</th><th>Резерв</th><th>Доступно</th></tr></thead><tbody>{stock.map((row) => <tr key={`${row.batch_id}-${row.cell_id}`}><td><strong>{row.batch_number}</strong><small>SKU #{row.sku_id}</small></td><td><span className="address-chip">{row.address_code}</span></td><td><Status value={row.qc_status} /></td><td>{row.physical_quantity}</td><td>{row.reserved_quantity}</td><td><strong>{row.available_quantity}</strong></td></tr>)}</tbody></table></div>}
    </Panel>
  );
}

function Requests({ notify }) {
  const [form, setForm] = useState({ request_number: "", department_id: "", production_order: "", sku_id: "", quantity: "" });
  const [requestId, setRequestId] = useState("");
  const submit = async (event) => {
    event.preventDefault();
    try {
      const result = await request("/issue-requests", { method: "POST", body: JSON.stringify({ request_number: form.request_number, department_id: Number(form.department_id), production_order: form.production_order || null, lines: [{ sku_id: Number(form.sku_id), quantity: Number(form.quantity) }] }) });
      setRequestId(String(result.id));
      notify("success", `Требование создано: #${result.id}`);
    } catch (error) { notify("error", error.message); }
  };
  const reserve = async (allowPartial) => {
    if (!requestId) return notify("error", "Сначала создайте требование");
    try {
      const result = await request(`/issue-requests/${requestId}/reserve`, { method: "POST", body: JSON.stringify({ allow_partial: allowPartial }) });
      notify("success", `Резервирование завершено: ${result.status}`);
    } catch (error) { notify("error", error.message); }
  };
  return <Panel title="Требование М-11" subtitle="Заявка цеха и FIFO/FEFO-резервирование"><form onSubmit={submit}><div className="form-row"><Field label="Номер требования" value={form.request_number} onChange={(v) => setForm({ ...form, request_number: v })} placeholder="М11-2026-001" /><Field label="ID цеха" type="number" value={form.department_id} onChange={(v) => setForm({ ...form, department_id: v })} /></div><Field label="Производственный заказ" value={form.production_order} onChange={(v) => setForm({ ...form, production_order: v })} placeholder="ЦНС-001" /><div className="form-row"><Field label="ID материала" type="number" value={form.sku_id} onChange={(v) => setForm({ ...form, sku_id: v })} /><Field label="Количество" type="number" step="0.001" value={form.quantity} onChange={(v) => setForm({ ...form, quantity: v })} /></div><div className="button-row"><Button type="submit">Создать требование</Button><Button type="button" kind="secondary" onClick={() => reserve(false)}>Резервировать FIFO</Button><Button type="button" kind="ghost" onClick={() => reserve(true)}>Разрешить частичный резерв</Button></div></form>{requestId && <div className="inline-result">Текущее требование: <strong>#{requestId}</strong></div>}</Panel>;
}

function Status({ value }) {
  const labels = { ACCEPTED: "Годен", UNDER_CONTROL: "ОТК", REJECTED_QUARANTINE: "Брак / изолятор" };
  const kind = value === "ACCEPTED" ? "ok" : value === "REJECTED_QUARANTINE" ? "danger" : "pending";
  return <span className={`status status-${kind}`}>{labels[value] || value}</span>;
}

export default App;
