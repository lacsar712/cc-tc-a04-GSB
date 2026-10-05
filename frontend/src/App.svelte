<script>
  import { onMount, onDestroy } from "svelte";

  let session = null;
  let page = "logs";
  let logs = [];
  let pairings = [];
  let loginUser = "surveyor";
  let loginPass = "surv123456";
  let section = "";
  let leftMm = "";
  let rightMm = "";
  let pairSection = "";
  let pairLeft = "";
  let pairRight = "";
  let pairThreshold = "0.5";
  let editId = null;
  let editSection = "";
  let editLeft = "";
  let editRight = "";
  let editThreshold = "";
  let error = "";
  let dualError = "";
  let loading = false;
  let timer;

  $: isWriter = session?.role === "writer";
  $: rejections = logs.filter((r) => r.status === "rejected");

  function syncPage() {
    page = location.hash === "#/dual" ? "dual" : "logs";
  }

  function headers() {
    return session ? { Authorization: "Bearer " + session.token } : {};
  }

  async function refresh() {
    if (!session) return;
    const [logsRes, pairRes] = await Promise.all([
      fetch("/api/logs", { headers: headers() }),
      fetch("/api/pairings", { headers: headers() }),
    ]);
    if (logsRes.status === 401 || pairRes.status === 401) {
      logout();
      return;
    }
    if (logsRes.ok) logs = await logsRes.json();
    if (pairRes.ok) pairings = await pairRes.json();
  }

  async function login() {
    error = "";
    loading = true;
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: loginUser, password: loginPass }),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "登录失败";
        return;
      }
      session = { token: data.access_token, username: data.username, role: data.role };
      localStorage.setItem("tunnel_session", JSON.stringify(session));
      await refresh();
      timer = setInterval(refresh, 2000);
    } catch {
      error = "无法连接接口";
    } finally {
      loading = false;
    }
  }

  function logout() {
    if (timer) clearInterval(timer);
    session = null;
    logs = [];
    pairings = [];
    localStorage.removeItem("tunnel_session");
  }

  async function submit() {
    error = "";
    loading = true;
    try {
      const res = await fetch("/api/logs", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers() },
        body: JSON.stringify({
          section,
          left_mm: Number(leftMm),
          right_mm: Number(rightMm),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "提交失败";
        await refresh();
        return;
      }
      leftMm = "";
      rightMm = "";
      await refresh();
    } catch {
      error = "提交时网络异常";
    } finally {
      loading = false;
    }
  }

  async function registerPairing() {
    dualError = "";
    loading = true;
    try {
      const res = await fetch("/api/pairings", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers() },
        body: JSON.stringify({
          section: pairSection,
          left_gauge: pairLeft,
          right_gauge: pairRight,
          threshold_mm: Number(pairThreshold),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        dualError = data.detail || "登记失败";
        return;
      }
      pairSection = "";
      pairLeft = "";
      pairRight = "";
      pairThreshold = "0.5";
      await refresh();
    } catch {
      dualError = "登记时网络异常";
    } finally {
      loading = false;
    }
  }

  function startEdit(p) {
    editId = p.id;
    editSection = p.section;
    editLeft = p.left_gauge;
    editRight = p.right_gauge;
    editThreshold = String(p.threshold_mm);
  }

  async function saveEdit() {
    dualError = "";
    loading = true;
    try {
      const res = await fetch("/api/pairings/" + editId, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...headers() },
        body: JSON.stringify({
          section: editSection,
          left_gauge: editLeft,
          right_gauge: editRight,
          threshold_mm: Number(editThreshold),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        dualError = data.detail || "保存失败";
        return;
      }
      editId = null;
      await refresh();
    } catch {
      dualError = "保存时网络异常";
    } finally {
      loading = false;
    }
  }

  function fmtTime(iso) {
    return iso ? iso.replace("T", " ").slice(0, 19) : "—";
  }

  onMount(() => {
    syncPage();
    window.addEventListener("hashchange", syncPage);
    const raw = localStorage.getItem("tunnel_session");
    if (raw) {
      try {
        session = JSON.parse(raw);
        refresh();
        timer = setInterval(refresh, 2000);
      } catch {
        localStorage.removeItem("tunnel_session");
      }
    }
  });

  onDestroy(() => {
    window.removeEventListener("hashchange", syncPage);
    if (timer) clearInterval(timer);
  });
</script>

<header class="topbar">
  <h1>隧道收敛测缝台</h1>
  {#if session}
    <nav>
      <a href="#/" class:active={page === "logs"}>测量记录</a>
      <a href="#/dual" class:active={page === "dual"}>双路专页</a>
    </nav>
  {/if}
</header>

<main>
  {#if !session}
    <p class="sub">
      测量员一次提交拱顶左右两路读数，左右差值绝对值越过登记表门槛即整份退回并写明双路超差。
      登录框已预填可写账号 surveyor / surv123456。
    </p>
    <section>
      <label>用户名</label>
      <input bind:value={loginUser} autocomplete="off" />
      <label>密码</label>
      <input type="password" bind:value={loginPass} autocomplete="off" />
      <button disabled={loading} on:click={login}>登录</button>
      {#if error}<p class="err">{error}</p>{/if}
    </section>
  {:else}
    <p class="sub">
      已登录：{session.username}（{isWriter ? "测量员，可提交" : "巡检员，只读：能看配对和差值，不许改配对也不能报"}）
      <button class="link" on:click={logout}>退出</button>
    </p>

    {#if page === "logs"}
      {#if isWriter}
        <section>
          <h2>提交双路读数</h2>
          <label>断面（须先在双路专页绑左右配对，对不上不许进队）</label>
          <select bind:value={section}>
            <option value="" disabled>选择已登记断面</option>
            {#each pairings as p}
              <option value={p.section}>{p.section}（{p.left_gauge} / {p.right_gauge}，门槛 {p.threshold_mm} mm）</option>
            {/each}
          </select>
          <div class="cols">
            <div>
              <label>左路读数（毫米）</label>
              <input type="number" step="0.1" bind:value={leftMm} />
            </div>
            <div>
              <label>右路读数（毫米）</label>
              <input type="number" step="0.1" bind:value={rightMm} />
            </div>
          </div>
          <button disabled={loading || !section} on:click={submit}>提交（进入待认领）</button>
          {#if error}<p class="err">{error}</p>{/if}
        </section>
      {/if}
      <section>
        <h2>测量记录 <button class="link" disabled={loading} on:click={refresh}>刷新</button></h2>
        <table>
          <thead>
            <tr>
              <th>编号</th><th>断面</th><th>左mm</th><th>右mm</th><th>差值mm</th>
              <th>随单冻结配对</th><th>状态</th><th>结论</th><th>说明</th>
            </tr>
          </thead>
          <tbody>
            {#each logs as row}
              <tr>
                <td>{row.id}</td>
                <td>{row.section}</td>
                <td>{row.left_mm}</td>
                <td>{row.right_mm}</td>
                <td>{row.diff_mm}</td>
                <td>
                  {#if row.pair_left_gauge}
                    {row.pair_left_gauge} / {row.pair_right_gauge}（门槛 {row.pair_threshold_mm}）
                  {:else}—{/if}
                </td>
                <td>
                  <span class="tag {row.status === 'pending' ? 'pending' : row.status === 'rejected' ? 'bad' : 'ok'}">
                    {row.status_label}
                  </span>
                </td>
                <td>
                  {#if row.verdict}
                    <span class="tag {row.verdict === '合格' ? 'ok' : 'bad'}">{row.verdict}</span>
                  {:else}—{/if}
                </td>
                <td>{row.reason ?? "—"}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </section>
    {:else}
      {#if isWriter}
        <section>
          <h2>登记左右配对</h2>
          <div class="cols">
            <div>
              <label>断面</label>
              <input placeholder="例如 甲" bind:value={pairSection} />
            </div>
            <div>
              <label>差值门槛（毫米）</label>
              <input type="number" step="0.1" min="0.1" bind:value={pairThreshold} />
            </div>
          </div>
          <div class="cols">
            <div>
              <label>左支编号</label>
              <input placeholder="例如 CJ-L-001" bind:value={pairLeft} />
            </div>
            <div>
              <label>右支编号</label>
              <input placeholder="例如 CJ-R-001" bind:value={pairRight} />
            </div>
          </div>
          <button disabled={loading} on:click={registerPairing}>登记配对</button>
          {#if dualError}<p class="err">{dualError}</p>{/if}
        </section>
      {/if}
      <section>
        <h2>配对登记表</h2>
        <table>
          <thead>
            <tr>
              <th>编号</th><th>断面</th><th>左支编号</th><th>右支编号</th>
              <th>差值门槛mm</th><th>登记人</th><th>更新时间</th>
              {#if isWriter}<th>操作</th>{/if}
            </tr>
          </thead>
          <tbody>
            {#each pairings as p}
              <tr>
                {#if editId === p.id}
                  <td>{p.id}</td>
                  <td><input class="cell" bind:value={editSection} /></td>
                  <td><input class="cell" bind:value={editLeft} /></td>
                  <td><input class="cell" bind:value={editRight} /></td>
                  <td><input class="cell" type="number" step="0.1" bind:value={editThreshold} /></td>
                  <td>{p.created_by}</td>
                  <td>{fmtTime(p.updated_at)}</td>
                  <td>
                    <button disabled={loading} on:click={saveEdit}>保存</button>
                    <button class="secondary" on:click={() => (editId = null)}>取消</button>
                  </td>
                {:else}
                  <td>{p.id}</td>
                  <td>{p.section}</td>
                  <td>{p.left_gauge}</td>
                  <td>{p.right_gauge}</td>
                  <td>{p.threshold_mm}</td>
                  <td>{p.created_by}</td>
                  <td>{fmtTime(p.updated_at)}</td>
                  {#if isWriter}
                    <td><button class="secondary" on:click={() => startEdit(p)}>改</button></td>
                  {/if}
                {/if}
              </tr>
            {/each}
            {#if pairings.length === 0}
              <tr><td colspan="8" class="muted">尚未登记任何断面配对</td></tr>
            {/if}
          </tbody>
        </table>
        <p class="muted">登记表改动只影响之后的新单；旧单配对随单冻结，仍按提交时的快照判定。</p>
      </section>
      <section>
        <h2>拒收例子总表</h2>
        <table>
          <thead>
            <tr>
              <th>编号</th><th>断面</th><th>左mm</th><th>右mm</th><th>差值mm</th>
              <th>冻结门槛mm</th><th>退回原因</th><th>提交人</th><th>时间</th>
            </tr>
          </thead>
          <tbody>
            {#each rejections as row}
              <tr>
                <td>{row.id}</td>
                <td>{row.section}</td>
                <td>{row.left_mm}</td>
                <td>{row.right_mm}</td>
                <td>{row.diff_mm}</td>
                <td>{row.pair_threshold_mm}</td>
                <td>{row.reason}</td>
                <td>{row.created_by}</td>
                <td>{fmtTime(row.created_at)}</td>
              </tr>
            {/each}
            {#if rejections.length === 0}
              <tr><td colspan="9" class="muted">暂无拒收例子</td></tr>
            {/if}
          </tbody>
        </table>
      </section>
    {/if}
  {/if}
</main>

<style>
  :global(body) {
    margin: 0;
    font-family: "Segoe UI", system-ui, sans-serif;
    background: #1c1917;
    color: #f5f5f4;
  }
  .topbar {
    display: flex; align-items: center; gap: 1.5rem;
    padding: 0.75rem 1.5rem; background: #0c0a09; border-bottom: 1px solid #44403c;
  }
  .topbar h1 { color: #fbbf24; margin: 0; font-size: 1.25rem; }
  .topbar nav { display: flex; gap: 0.5rem; }
  .topbar nav a {
    color: #d6d3d1; text-decoration: none; padding: 0.35rem 0.9rem;
    border-radius: 6px; border: 1px solid #44403c;
  }
  .topbar nav a.active { background: #d97706; color: #fff; border-color: #d97706; }
  main { max-width: 1100px; margin: 0 auto; padding: 1.5rem; }
  .sub { color: #a8a29e; margin-bottom: 1.25rem; }
  section {
    background: #292524; border: 1px solid #44403c; border-radius: 8px;
    padding: 1rem 1.25rem; margin-bottom: 1rem;
  }
  h2 { font-size: 1rem; margin: 0 0 0.75rem; color: #fde68a; }
  label { display: block; font-size: 0.85rem; color: #d6d3d1; margin-bottom: 0.25rem; }
  input, select {
    width: 100%; box-sizing: border-box; padding: 0.5rem 0.65rem; border-radius: 6px;
    border: 1px solid #57534e; background: #0c0a09; color: #fafaf9; margin-bottom: 0.75rem;
  }
  input.cell { margin-bottom: 0; padding: 0.3rem 0.45rem; }
  .cols { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
  button {
    cursor: pointer; padding: 0.5rem 1rem; border: none; border-radius: 6px;
    background: #d97706; color: #fff; font-weight: 600;
  }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  button.secondary { background: #57534e; }
  button.link {
    background: none; color: #fbbf24; padding: 0 0.25rem; font-weight: 400;
    text-decoration: underline;
  }
  .err { color: #fb7185; }
  .muted { color: #78716c; font-size: 0.85rem; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th, td { text-align: left; padding: 0.45rem; border-bottom: 1px solid #44403c; }
  .tag { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.8rem; white-space: nowrap; }
  .ok { background: #14532d; color: #86efac; }
  .bad { background: #7f1d1d; color: #fca5a5; }
  .pending { background: #713f12; color: #fde68a; }
</style>
