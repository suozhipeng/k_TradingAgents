/** Data Hub — JS API integration for data_hub.html */
async function dhRefresh() {
  document.getElementById('dh-status-badge').textContent = '加载中...';
  try {
    const res = await fetch('/api/v1/setup/status');
    const data = await res.json();
    const tables = data.tables || {};
    const tableNames = Object.keys(tables).filter(k => !k.startsWith('_'));
    const totalRows = tableNames.reduce((s, k) => s + (tables[k].rows || 0), 0);

    document.getElementById('dh-tables').textContent = tableNames.length;
    document.getElementById('dh-rows').textContent = totalRows.toLocaleString();
    document.getElementById('dh-initialized').textContent = data.has_real_data ? '✅ 是' : '❌ 否';
    document.getElementById('dh-status-badge').textContent = data.status === 'ok' ? '✅ 正常' : '⚠️ 未初始化';

    const tbody = document.getElementById('dh-table-body');
    tbody.innerHTML = '';
    for (const name of tableNames) {
      const info = tables[name];
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${name}</td><td>${(info.rows || 0).toLocaleString()}</td><td class="${info.schema_ok ? 'dh-status-ok' : 'dh-status-warn'}">${info.schema_ok ? '✅' : '⚠️'}</td>`;
      tbody.appendChild(tr);
    }
  } catch (e) {
    document.getElementById('dh-status-badge').textContent = '❌ 错误';
    const msg = document.getElementById('dh-status-message');
    msg.className = 'dh-status dh-status-err';
    msg.textContent = '无法加载数据状态: ' + e.message;
  }
}

async function dhBootstrap() {
  const msg = document.getElementById('dh-status-message');
  msg.className = 'dh-status';
  msg.textContent = '正在初始化...';
  try {
    const res = await fetch('/api/v1/setup/bootstrap', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      msg.className = 'dh-status dh-status-ok';
      msg.textContent = '✅ ' + (data.note || '初始化完成');
    } else {
      msg.className = 'dh-status dh-status-err';
      msg.textContent = '❌ ' + (data.error || '初始化失败');
    }
    dhRefresh();
  } catch (e) {
    msg.className = 'dh-status dh-status-err';
    msg.textContent = '❌ 请求失败: ' + e.message;
  }
}

document.addEventListener('DOMContentLoaded', dhRefresh);
