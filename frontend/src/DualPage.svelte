<script>
  import { onDestroy } from "svelte";

  export let session;
  export let isWriter;
  export let onLogout;

  let pairings = [];
  let reports = [];
  let error = "";
  let info = "";
  let loading = false;

  let regSection = "";
  let regLeftNo = "";
  let regRightNo = "";
  let regThreshold = "3.0";
  let editingId = null;

  let repSection = "";
  let repLeft = "";
  let repRight = "";

  let timer = setInterval(load, 2000);
  load();
  onDestroy(() => clearInterval(timer));

  $: rejected = reports.filter((r) => r.status === "rejected");
  $: currentPairing = pairings.find((p) => p.section === repSection);

  function headers() {
    return { Authorization: "Bearer " + session.token };
  }

  async function load() {
    const [pRes, rRes] = await Promise.all([
      fetch("/api/pairings", { headers: headers() }),
      fetch("/api/dual-reports", { headers: headers() }),
    ]);
    if (pRes.status === 401 || rRes.status === 401) {
      onLogout();
      return;
    }
    if (pRes.ok) pairings = await pRes.json();
    if (rRes.ok) reports = await rRes.json();
  }

  async function savePairing() {
    error = "";
    info = "";
    loading = true;
    const body = {
      section: regSection,
      left_no: regLeftNo,
      right_no: regRightNo,
      threshold_mm: Number(regThreshold),
    };
    try {
      const res = await fetch(
        editingId ? "/api/pairings/" + editingId : "/api/pairings",
        {
          method: editingId ? "PUT" : "POST",
          headers: { "Content-Type": "application/json", ...headers() },
          body: JSON.stringify(body),
        }
      );
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "登记失败";
        return;
      }
      info = editingId
        ? `已修改断面 ${data.section} 的配对（旧单配对仍冻结）`
        : `已登记断面 ${data.section} 的左右配对`;
      cancelEdit();
      await load();
    } catch {
      error = "登记时网络异常";
    } finally {
      loading = false;
    }
  }

  function editPairing(p) {
    editingId = p.id;
    regSection = p.section;
    regLeftNo = p.left_no;
    regRightNo = p.right_no;
    regThreshold = String(p.threshold_mm);
    error = "";
    info = "";
  }

  function cancelEdit() {
    editingId = null;
    regSection = "";
    regLeftNo = "";
    regRightNo = "";
    regThreshold = "3.0";
  }

  async function submitReport() {
    error = "";
    info = "";
    loading = true;
    try {
      const res = await fetch("/api/dual-reports", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers() },
        body: JSON.stringify({
          section: repSection,
          left_mm: Number(repLeft),
          right_mm: Number(repRight),
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        error = data.detail || "提交失败";
        return;
      }
      info =
        data.status === "rejected"
          ? `第 ${data.id} 单已整份退回：${data.reason}`
          : `第 ${data.id} 单已进入待认领（差值 ${data.diff_mm} mm）`;
      repLeft = "";
      repRight = "";
      await load();
    } catch {
      error = "提交时网络异常";
    } finally {
      loading = false;
    }
  }

  const STATUS = {
    pending: { text: "待认领", cls: "pending" },
    rejected: { text: "已退回", cls: "bad" },
    done: { text: "已完成", cls: "ok" },
  };

  function statusTag(s) {
    return STATUS[s] || { text: s, cls: "pending" };
  }
</script>

<style>
  section {
    background: #292524; border: 1px solid #44403c; border-radius: 8px;
    padding: 1rem 1.25rem; margin-bottom: 1rem;
  }
  h2 { font-size: 1.05rem; color: #fcd34d; margin: 0 0 0.75rem; }
  .sub { color: #a8a29e; margin-bottom: 1.25rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0 0.75rem; }
  label { display: block; font-size: 0.85rem; color: #d6d3d1; margin-bottom: 0.25rem; }
  input, select {
    width: 100%; box-sizing: border-box; padding: 0.5rem 0.65rem; border-radius: 6px;
    border: 1px solid #57534e; background: #0c0a09; color: #fafaf9; margin-bottom: 0.75rem;
  }
  button {
    cursor: pointer; padding: 0.5rem 1rem; border: none; border-radius: 6px;
    background: #d97706; color: #fff; font-weight: 600;
  }
  button.secondary { background: #57534e; }
  button.small { padding: 0.25rem 0.6rem; font-size: 0.8rem; }
  .err { color: #fb7185; }
  .ok-msg { color: #86efac; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th, td { text-align: left; padding: 0.45rem; border-bottom: 1px solid #44403c; }
  .tag { padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.8rem; }
  .ok { background: #14532d; color: #86efac; }
  .bad { background: #7f1d1d; color: #fca5a5; }
  .pending { background: #713f12; color: #fde68a; }
  .hint { color: #a8a29e; font-size: 0.85rem; }
</style>

<p class="sub">
  双路专页：登记拱顶左右两支测缝计配对与差值门槛，双路上报超差整份退回。已登录：{session.username}（{isWriter ? "可提交" : "只读"}）
</p>

{#if isWriter}
  <section>
    <h2>{editingId ? "修改配对（旧单配对仍冻结）" : "配对登记"}</h2>
    <div class="grid">
      <div>
        <label>断面</label>
        <input placeholder="例如 甲断面" bind:value={regSection} />
      </div>
      <div>
        <label>左支编号</label>
        <input placeholder="例如 JL-L-01" bind:value={regLeftNo} />
      </div>
      <div>
        <label>右支编号</label>
        <input placeholder="例如 JL-R-01" bind:value={regRightNo} />
      </div>
      <div>
        <label>差值门槛（毫米）</label>
        <input type="number" step="0.1" min="0" bind:value={regThreshold} />
      </div>
    </div>
    <button disabled={loading} on:click={savePairing}>
      {editingId ? "保存修改" : "登记配对"}
    </button>
    {#if editingId}
      <button class="secondary" on:click={cancelEdit}>取消修改</button>
    {/if}
  </section>
{/if}

<section>
  <h2>已登记配对</h2>
  {#if pairings.length === 0}
    <p class="hint">尚未登记任何配对。</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>断面</th><th>左支编号</th><th>右支编号</th><th>差值门槛mm</th>
          <th>登记人</th><th>更新时间</th>{#if isWriter}<th>操作</th>{/if}
        </tr>
      </thead>
      <tbody>
        {#each pairings as p}
          <tr>
            <td>{p.section}</td>
            <td>{p.left_no}</td>
            <td>{p.right_no}</td>
            <td>{p.threshold_mm}</td>
            <td>{p.created_by}</td>
            <td>{p.updated_at ? p.updated_at.slice(0, 19).replace("T", " ") : "—"}</td>
            {#if isWriter}
              <td><button class="small secondary" on:click={() => editPairing(p)}>修改</button></td>
            {/if}
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>

{#if isWriter}
  <section>
    <h2>双路上报（一次交左右两路）</h2>
    <div class="grid">
      <div>
        <label>断面</label>
        <select bind:value={repSection}>
          <option value="">请选择已登记断面</option>
          {#each pairings as p}
            <option value={p.section}>{p.section}（{p.left_no} ~ {p.right_no}）</option>
          {/each}
        </select>
      </div>
      <div>
        <label>左路读数（毫米）</label>
        <input type="number" step="0.1" bind:value={repLeft} />
      </div>
      <div>
        <label>右路读数（毫米）</label>
        <input type="number" step="0.1" bind:value={repRight} />
      </div>
    </div>
    {#if currentPairing}
      <p class="hint">当前配对门槛：|左-右| ≤ {currentPairing.threshold_mm} mm，越过即整份退回并写明双路超差。</p>
    {/if}
    <button disabled={loading || !repSection} on:click={submitReport}>提交双路（进队并冻结配对）</button>
  </section>
{/if}

{#if error}<p class="err">{error}</p>{/if}
{#if info}<p class="ok-msg">{info}</p>{/if}

<section>
  <h2>双路报告</h2>
  {#if reports.length === 0}
    <p class="hint">暂无双路报告。</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>编号</th><th>断面</th><th>左mm</th><th>右mm</th><th>差值mm</th>
          <th>冻结配对</th><th>门槛mm</th><th>状态</th><th>结论</th><th>说明</th>
        </tr>
      </thead>
      <tbody>
        {#each reports as r}
          {@const st = statusTag(r.status)}
          <tr>
            <td>{r.id}</td>
            <td>{r.section}</td>
            <td>{r.left_mm}</td>
            <td>{r.right_mm}</td>
            <td>{r.diff_mm}</td>
            <td>{r.left_no} ~ {r.right_no}</td>
            <td>{r.threshold_mm}</td>
            <td><span class="tag {st.cls}">{st.text}</span></td>
            <td>
              {#if r.verdict}
                <span class="tag {r.verdict === '合格' ? 'ok' : 'bad'}">{r.verdict}</span>
              {:else}—{/if}
            </td>
            <td>{r.reason ?? "—"}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>

<section>
  <h2>拒收例子总表（{rejected.length} 例）</h2>
  {#if rejected.length === 0}
    <p class="hint">暂无拒收例子。</p>
  {:else}
    <table>
      <thead>
        <tr>
          <th>编号</th><th>断面</th><th>左mm</th><th>右mm</th><th>差值mm</th>
          <th>门槛mm</th><th>退回说明</th><th>时间</th>
        </tr>
      </thead>
      <tbody>
        {#each rejected as r}
          <tr>
            <td>{r.id}</td>
            <td>{r.section}</td>
            <td>{r.left_mm}</td>
            <td>{r.right_mm}</td>
            <td>{r.diff_mm}</td>
            <td>{r.threshold_mm}</td>
            <td>{r.reason}</td>
            <td>{r.created_at ? r.created_at.slice(0, 19).replace("T", " ") : "—"}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>
