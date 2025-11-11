const STATUSES = {
  awaiting_payment: { label: 'Ожидает оплаты', color: '#fbbf24', emoji: '⏳' },
  paid: { label: 'Оплачено', color: '#34d399', emoji: '💰' },
  in_progress: { label: 'В процессе', color: '#60a5fa', emoji: '🔄' },
  completed: { label: 'Завершено', color: '#22c55e', emoji: '✅' },
  cancelled: { label: 'Отменено', color: '#f87171', emoji: '❌' }
};

const PACKAGE_LABELS = {
  single: 'Single Test',
  mini: 'Mini Audit',
  retainer: 'Retainer',
  custom: 'Custom'
};

const STORAGE_KEYS = {
  filters: 'paymentqa:orders_filters',
  pageSize: 'paymentqa:page_size'
};

const state = {
  orders: [],
  testers: [],
  activity: [],
  countries: {},
  filters: {
    query: '',
    statuses: new Set(Object.keys(STATUSES)),
    package: 'all',
    geo: new Set(),
    period: '30',
    from: null,
    to: null,
    tester: 'all',
    amountFrom: null,
    amountTo: null
  },
  metricsRange: 30,
  metricsCustomRange: null,
  sort: { key: 'createdAt', direction: 'desc' },
  page: 1,
  pageSize: 25,
  selected: new Set(),
  charts: {},
  lastSync: new Date()
};

const currencyFormatter = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'EUR',
  maximumFractionDigits: 0
});

const numberFormatter = new Intl.NumberFormat('ru-RU');

const durationFormatter = new Intl.RelativeTimeFormat('ru', { style: 'short' });

const EVENT_ICONS = {
  order_created: '🆕',
  order_paid: '💰',
  payment_proof_received: '🧾',
  status_changed: '🔁',
  tester_assigned: '👩‍💻',
  tester_unassigned: '🚫',
  report_uploaded: '📄',
  order_completed: '✅',
  order_cancelled: '❌',
  note_added: '📝',
  tester_created: '➕',
  admin_action: '⚙️'
};

const CHART_COLORS = {
  awaiting_payment: '#f59e0b',
  paid: '#34d399',
  in_progress: '#3b82f6',
  completed: '#059669',
  cancelled: '#ef4444'
};

const PACKAGE_COLORS = ['#d8b4fe', '#c084fc', '#a855f7'];

async function hydrateData() {
  const data = await window.PaymentQA.loadData();
  window.PaymentQA_DATA = data;

  const orders = Array.isArray(data.orders) ? data.orders : [];
  state.orders = orders.map((order) => ({
    ...order,
    createdAt: order.createdAt ? new Date(order.createdAt) : new Date(),
    paidAt: order.paidAt ? new Date(order.paidAt) : null,
    startedAt: order.startedAt ? new Date(order.startedAt) : null,
    completedAt: order.completedAt ? new Date(order.completedAt) : null
  }));
  state.testers = Array.isArray(data.testers) ? data.testers : [];
  state.activity = (Array.isArray(data.activity) ? data.activity : [])
    .map((item) => ({ ...item, createdAt: item.createdAt ? new Date(item.createdAt) : new Date() }))
    .sort((a, b) => b.createdAt - a.createdAt);
  state.countries = data.countries || {};
  state.lastSync = new Date();
  updateLastSyncLabel();
}

function updateLastSyncLabel() {
  const el = document.getElementById('last-sync');
  if (!el || !state.lastSync) return;
  const diffMinutes = Math.round((Date.now() - state.lastSync.getTime()) / 60000);
  if (diffMinutes <= 0) {
    el.textContent = 'только что';
  } else {
    el.textContent = durationFormatter.format(-diffMinutes, 'minute');
  }
}

async function init() {
  try {
    await hydrateData();
  } catch (error) {
    console.error('Не удалось загрузить данные панели', error);
    const grid = document.getElementById('metrics-grid');
    if (grid) grid.innerHTML = '<p class="error">Не удалось загрузить данные. Попробуйте обновить страницу.</p>';
    return;
  }

  hydrateFilters();
  hydratePageSize();
  buildStatusChips();
  populateGeoSelect();
  populateTesterSelect();
  syncFiltersForm();
  attachEventListeners();
  renderAll();

  setInterval(updateLastSyncLabel, 30000);
}

function hydrateFilters() {
  const saved = localStorage.getItem(STORAGE_KEYS.filters);
  if (saved) {
    try {
      const parsed = JSON.parse(saved);
      if (parsed.query) state.filters.query = parsed.query;
      if (Array.isArray(parsed.statuses)) state.filters.statuses = new Set(parsed.statuses);
      if (parsed.package) state.filters.package = parsed.package;
      if (Array.isArray(parsed.geo)) state.filters.geo = new Set(parsed.geo);
      if (parsed.period) state.filters.period = parsed.period;
      if (parsed.from) state.filters.from = parsed.from;
      if (parsed.to) state.filters.to = parsed.to;
      if (parsed.tester) state.filters.tester = parsed.tester;
      if (parsed.amountFrom !== undefined) state.filters.amountFrom = parsed.amountFrom;
      if (parsed.amountTo !== undefined) state.filters.amountTo = parsed.amountTo;
    } catch (error) {
      console.warn('Не удалось загрузить фильтры из localStorage', error);
    }
  }
}

function hydratePageSize() {
  const saved = localStorage.getItem(STORAGE_KEYS.pageSize);
  if (saved) {
    state.pageSize = Number(saved) || 25;
  }
}

function attachEventListeners() {
  document.getElementById('refresh-data').addEventListener('click', async () => {
    try {
      await hydrateData();
      renderAll();
      showToast('🔄', 'Данные обновлены');
    } catch (error) {
      console.error('Ошибка при обновлении данных', error);
      showToast('⚠️', 'Не удалось обновить данные');
    }
  });

  document.getElementById('export-dashboard').addEventListener('click', () => {
    downloadDashboardSummary();
  });

  document.getElementById('save-filters').addEventListener('click', () => {
    persistFilters();
    showToast('💾', 'Фильтры сохранены');
  });

  document.getElementById('reset-filters').addEventListener('click', () => {
    resetFilters();
    showToast('♻️', 'Фильтры сброшены');
  });

  document.getElementById('export-orders').addEventListener('click', () => {
    exportOrdersToCsv();
  });

  document.getElementById('bulk-export').addEventListener('click', () => {
    exportOrdersToCsv([...state.selected]);
  });

  document.getElementById('bulk-delete').addEventListener('click', () => {
    if (!state.selected.size) return;
    if (confirm('Удалить выбранные заказы? Это действие нельзя отменить.')) {
      state.orders = state.orders.filter((order) => !state.selected.has(order.id));
      state.selected.clear();
      renderAll();
      showToast('🗑️', 'Выбранные заказы удалены (демо).');
    }
  });

  document.getElementById('bulk-clear').addEventListener('click', () => {
    state.selected.clear();
    renderSelected();
  });

  document.getElementById('bulk-status').addEventListener('change', async (event) => {
    const newStatus = event.target.value;
    if (!newStatus) return;
    const ids = [...state.selected];
    if (!ids.length) return;
    for (const id of ids) {
      const order = state.orders.find((item) => item.id === id);
      if (!order) continue;
      const now = new Date();
      order.status = newStatus;
      if (newStatus === 'paid') order.paidAt = now;
      if (newStatus === 'in_progress') order.startedAt = now;
      if (newStatus === 'completed') order.completedAt = now;
      if (newStatus === 'cancelled') order.cancelledAt = now;
      try {
        await window.PaymentQA.updateOrderStatus(order.id, { status: newStatus });
      } catch (error) {
        console.error('Не удалось обновить статус заказа', error);
      }
    }
    showToast('✅', `Статусы обновлены для ${ids.length} заказов.`);
    renderAll();
    event.target.value = '';
  });

  document.getElementById('bulk-tester').addEventListener('change', (event) => {
    const testerId = event.target.value;
    if (!testerId) return;
    state.selected.forEach((id) => {
      const order = state.orders.find((item) => item.id === id);
      if (order) {
        order.testerId = testerId === 'none' ? null : Number(testerId);
      }
    });
    showToast('👩‍💻', 'Назначение тестера обновлено (демо).');
    renderAll();
    event.target.value = '';
  });

  document.getElementById('page-size').addEventListener('change', (event) => {
    state.pageSize = Number(event.target.value);
    state.page = 1;
    localStorage.setItem(STORAGE_KEYS.pageSize, String(state.pageSize));
    renderOrders();
  });

  document.getElementById('chart-period').addEventListener('change', (event) => {
    const value = event.target.value;
    state.metricsRange = value === 'custom' ? 'custom' : Number(value);
    renderCharts();
    renderMetrics();
  });

  document.getElementById('apply-chart-range').addEventListener('click', () => {
    const from = document.getElementById('chart-from').value;
    const to = document.getElementById('chart-to').value;
    if (from && to) {
      state.metricsRange = 'custom';
      state.metricsCustomRange = { from: new Date(from), to: new Date(`${to}T23:59:59`) };
      renderCharts();
      renderMetrics();
    }
  });

  document.querySelectorAll('.period-switcher button').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.period-switcher button').forEach((btn) => btn.classList.remove('is-active'));
      button.classList.add('is-active');
      if (button.dataset.range === 'custom') {
        const from = prompt('Дата начала (YYYY-MM-DD):');
        const to = prompt('Дата окончания (YYYY-MM-DD):');
        if (from && to) {
          state.metricsRange = 'custom';
          state.metricsCustomRange = { from: new Date(from), to: new Date(`${to}T23:59:59`) };
        }
      } else {
        state.metricsRange = Number(button.dataset.range);
        state.metricsCustomRange = null;
      }
      renderMetrics();
      renderCharts();
    });
  });

  document.getElementById('orders-filters').addEventListener('input', handleFilterChange);
  document.getElementById('orders-filters').addEventListener('change', handleFilterChange);

  document.getElementById('select-all').addEventListener('change', (event) => {
    const pageOrders = getPagedOrders().items;
    if (event.target.checked) {
      pageOrders.forEach((order) => state.selected.add(order.id));
    } else {
      pageOrders.forEach((order) => state.selected.delete(order.id));
    }
    renderSelected();
  });

  document.getElementById('activity-type').addEventListener('change', renderActivity);
  document.getElementById('activity-search').addEventListener('input', renderActivity);
  document.getElementById('export-activity').addEventListener('click', exportActivity);

  document.querySelectorAll('[data-close]').forEach((button) => {
    button.addEventListener('click', () => {
      const dialog = button.closest('dialog');
      dialog.close();
    });
  });

  document.getElementById('save-note').addEventListener('click', () => {
    showToast('📝', 'Заметка сохранена (демо).');
    document.getElementById('note-modal').close();
  });

  document.getElementById('confirm-status').addEventListener('click', () => {
    showToast('🔁', 'Статус обновлён (демо).');
    document.getElementById('status-modal').close();
  });

  document.querySelectorAll('[data-chart-download]').forEach((button) => {
    button.addEventListener('click', () => {
      const chartId = button.dataset.chartDownload;
      downloadChart(chartId);
    });
  });
}
function buildStatusChips() {
  const container = document.getElementById('status-chips');
  container.innerHTML = '';
  Object.entries(STATUSES).forEach(([key, value]) => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = `chip ${state.filters.statuses.has(key) ? 'is-active' : ''}`;
    chip.dataset.status = key;
    chip.innerHTML = `${value.emoji} ${value.label}`;
    chip.addEventListener('click', () => {
      if (state.filters.statuses.has(key)) {
        state.filters.statuses.delete(key);
      } else {
        state.filters.statuses.add(key);
      }
      chip.classList.toggle('is-active');
      renderOrders();
      renderMetrics();
      renderCharts();
    });
    container.appendChild(chip);
  });
}

function populateGeoSelect() {
  const select = document.getElementById('geo-select');
  select.innerHTML = '';
  Object.entries(state.countries)
    .sort((a, b) => a[1].name.localeCompare(b[1].name))
    .forEach(([code, info]) => {
      const option = document.createElement('option');
      option.value = code;
      option.textContent = `${info.flag} ${info.name}`;
      if (state.filters.geo.has(code)) option.selected = true;
      select.appendChild(option);
    });
}

function populateTesterSelect() {
  const select = document.getElementById('tester-select');
  state.testers.forEach((tester) => {
    const option = document.createElement('option');
    option.value = tester.id;
    option.textContent = `${tester.name} (${tester.geoFocus})`;
    if (String(state.filters.tester) === String(tester.id)) option.selected = true;
    select.appendChild(option);
  });

  const bulkSelect = document.getElementById('bulk-tester');
  state.testers.forEach((tester) => {
    const option = document.createElement('option');
    option.value = tester.id;
    option.textContent = tester.name;
    bulkSelect.appendChild(option);
  });
}

function syncFiltersForm() {
  const form = document.getElementById('orders-filters');
  form.query.value = state.filters.query;
  form.package.value = state.filters.package;
  form.period.value = state.filters.period;
  form.from.value = state.filters.from || '';
  form.to.value = state.filters.to || '';
  form.tester.value = state.filters.tester;
  form.amount_from.value = state.filters.amountFrom ?? '';
  form.amount_to.value = state.filters.amountTo ?? '';
  [...form.geo.options].forEach((option) => {
    option.selected = state.filters.geo.has(option.value);
  });
}

function handleFilterChange(event) {
  const form = event.currentTarget;
  state.filters.query = form.query.value.trim();
  state.filters.package = form.package.value;
  state.filters.period = form.period.value;
  state.filters.from = form.from.value || null;
  state.filters.to = form.to.value || null;
  state.filters.tester = form.tester.value;
  state.filters.amountFrom = form.amount_from.value ? Number(form.amount_from.value) : null;
  state.filters.amountTo = form.amount_to.value ? Number(form.amount_to.value) : null;
  state.filters.geo = new Set([...form.geo.options].filter((opt) => opt.selected).map((opt) => opt.value));

  state.page = 1;
  renderOrders();
  renderMetrics();
  renderCharts();
}

function resetFilters() {
  state.filters = {
    query: '',
    statuses: new Set(Object.keys(STATUSES)),
    package: 'all',
    geo: new Set(),
    period: '30',
    from: null,
    to: null,
    tester: 'all',
    amountFrom: null,
    amountTo: null
  };
  persistFilters();
  document.getElementById('orders-filters').reset();
  buildStatusChips();
  populateGeoSelect();
  renderOrders();
  renderMetrics();
  renderCharts();
}

function persistFilters() {
  const payload = {
    query: state.filters.query,
    statuses: [...state.filters.statuses],
    package: state.filters.package,
    geo: [...state.filters.geo],
    period: state.filters.period,
    from: state.filters.from,
    to: state.filters.to,
    tester: state.filters.tester,
    amountFrom: state.filters.amountFrom,
    amountTo: state.filters.amountTo
  };
  localStorage.setItem(STORAGE_KEYS.filters, JSON.stringify(payload));
}

function renderAll() {
  renderMetrics();
  renderCharts();
  renderActivity();
  renderOrders();
  renderSelected();
}

function renderMetrics() {
  const grid = document.getElementById('metrics-grid');
  const metrics = calculateMetrics();
  const metricCards = createMetricCards(metrics);
  grid.innerHTML = '';
  metricCards.forEach((card) => grid.appendChild(card));
}
function calculateMetrics() {
  const now = new Date();
  let from;
  let to = now;
  if (state.metricsRange === 'custom' && state.metricsCustomRange) {
    from = state.metricsCustomRange.from;
    to = state.metricsCustomRange.to;
  } else {
    const range = state.metricsRange || 30;
    from = new Date(now);
    from.setDate(from.getDate() - range + 1);
  }

  const currentOrders = state.orders.filter((order) => order.createdAt >= from && order.createdAt <= to);
  const previousFrom = new Date(from);
  const previousTo = new Date(from);
  const previousRange = state.metricsRange === 'custom' && state.metricsCustomRange ? diffDays(state.metricsCustomRange) : state.metricsRange || 30;
  previousFrom.setDate(previousFrom.getDate() - previousRange);
  previousTo.setMilliseconds(previousTo.getMilliseconds() - 1);
  const previousOrders = state.orders.filter((order) => order.createdAt >= previousFrom && order.createdAt <= previousTo);

  const result = {};

  function makeMetric(id, title, value, previousValue, extra = {}) {
    const delta = previousValue ? ((value - previousValue) / previousValue) * 100 : value > 0 ? 100 : 0;
    const trend = delta > 1 ? 'up' : delta < -1 ? 'down' : 'flat';
    const deltaFormatted = `${delta > 0 ? '+' : ''}${delta.toFixed(1)}%`;
    return { id, title, value, previousValue, delta: deltaFormatted, trend, ...extra };
  }

  const revenueStatuses = ['paid', 'in_progress', 'completed'];
  const currentRevenueOrders = currentOrders.filter((order) => revenueStatuses.includes(order.status));
  const previousRevenueOrders = previousOrders.filter((order) => revenueStatuses.includes(order.status));

  const totalRevenue = currentRevenueOrders.reduce((acc, order) => acc + order.priceEur, 0);
  const previousRevenue = previousRevenueOrders.reduce((acc, order) => acc + order.priceEur, 0);
  result.totalRevenue = makeMetric('totalRevenue', 'Общий доход', totalRevenue, previousRevenue, {
    formatted: currencyFormatter.format(totalRevenue),
    icon: '💶'
  });

  const nowMonth = now.getMonth();
  const nowYear = now.getFullYear();
  const monthRevenueOrders = state.orders.filter(
    (order) =>
      order.paidAt &&
      order.paidAt.getMonth() === nowMonth &&
      order.paidAt.getFullYear() === nowYear &&
      revenueStatuses.includes(order.status)
  );
  const prevMonth = new Date(nowYear, nowMonth - 1, 1);
  const prevMonthOrders = state.orders.filter(
    (order) =>
      order.paidAt &&
      order.paidAt.getMonth() === prevMonth.getMonth() &&
      order.paidAt.getFullYear() === prevMonth.getFullYear() &&
      revenueStatuses.includes(order.status)
  );
  const monthRevenue = monthRevenueOrders.reduce((acc, order) => acc + order.priceEur, 0);
  const monthRevenuePrev = prevMonthOrders.reduce((acc, order) => acc + order.priceEur, 0);
  result.monthRevenue = makeMetric('monthRevenue', 'Доход за месяц', monthRevenue, monthRevenuePrev, {
    formatted: currencyFormatter.format(monthRevenue),
    icon: '📆'
  });

  const averageCheck = currentRevenueOrders.length ? totalRevenue / currentRevenueOrders.length : 0;
  const previousAverage = previousRevenueOrders.length ? previousRevenue / previousRevenueOrders.length : 0;
  result.averageCheck = makeMetric('averageCheck', 'Средний чек', averageCheck, previousAverage, {
    formatted: currencyFormatter.format(Math.round(averageCheck)),
    icon: '🧾'
  });

  const clientTotals = aggregateBy(state.orders, (order) => order.client.telegramId || order.client.username || order.id);
  const ltv = clientTotals.length ? clientTotals.reduce((acc, item) => acc + item.total, 0) / clientTotals.length : 0;
  result.ltv = makeMetric('ltv', 'LTV клиента', ltv, ltv * 0.85, {
    formatted: currencyFormatter.format(Math.round(ltv)),
    icon: '♾️'
  });

  const awaiting = currentOrders.filter((order) => order.status === 'awaiting_payment');
  const awaitingAmount = awaiting.reduce((acc, order) => acc + order.priceEur, 0);
  const prevAwaiting = previousOrders.filter((order) => order.status === 'awaiting_payment');
  const prevAwaitingAmount = prevAwaiting.reduce((acc, order) => acc + order.priceEur, 0);
  result.awaiting = makeMetric('awaiting', 'Ожидают оплаты', awaiting.length, prevAwaiting.length, {
    subtitle: `${currencyFormatter.format(awaitingAmount)}`,
    icon: '⏳'
  });

  const paid = currentOrders.filter((order) => order.status === 'paid');
  const paidAmount = paid.reduce((acc, order) => acc + order.priceEur, 0);
  const prevPaid = previousOrders.filter((order) => order.status === 'paid');
  const prevPaidAmount = prevPaid.reduce((acc, order) => acc + order.priceEur, 0);
  result.paid = makeMetric('paid', 'Оплачено', paid.length, prevPaid.length, {
    subtitle: currencyFormatter.format(paidAmount),
    icon: '💰'
  });

  const inProgress = currentOrders.filter((order) => order.status === 'in_progress');
  const prevInProgress = previousOrders.filter((order) => order.status === 'in_progress');
  result.inProgress = makeMetric('inProgress', 'В процессе', inProgress.length, prevInProgress.length, {
    icon: '🔄'
  });

  result.totalOrders = makeMetric('totalOrders', 'Всего заказов', currentOrders.length, previousOrders.length, {
    icon: '🧾'
  });

  const uniqueClients = new Set(state.orders.map((order) => order.client.telegramId || order.client.username));
  result.clientsTotal = makeMetric('clientsTotal', 'Всего клиентов', uniqueClients.size, uniqueClients.size - 2, {
    icon: '👥'
  });

  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const todaysOrders = state.orders.filter((order) => order.createdAt >= today);
  const todaysFirstOrders = new Set();
  todaysOrders.forEach((order) => {
    const clientId = order.client.telegramId || order.client.username;
    const firstOrder = state.orders
      .filter((item) => (item.client.telegramId || item.client.username) === clientId)
      .sort((a, b) => a.createdAt - b.createdAt)[0];
    if (firstOrder && firstOrder.id === order.id) {
      todaysFirstOrders.add(clientId);
    }
  });
  result.newToday = makeMetric('newToday', 'Новых за сегодня', todaysFirstOrders.size, todaysFirstOrders.size - 1, {
    icon: '✨'
  });

  const repeatClients = clientTotals.filter((client) => client.count > 1).length;
  const repeatPercent = uniqueClients.size ? (repeatClients / uniqueClients.size) * 100 : 0;
  result.repeat = makeMetric('repeat', 'Повторные покупки', repeatClients, repeatClients - 1, {
    subtitle: `${repeatPercent.toFixed(0)}% клиентов`,
    icon: '🔁'
  });

  const revenueCount = state.orders.filter((order) => revenueStatuses.includes(order.status)).length;
  const conversion = state.orders.length ? (revenueCount / state.orders.length) * 100 : 0;
  result.conversion = makeMetric('conversion', 'Конверсия старт→оплата', conversion, conversion - 3, {
    formatted: `${conversion.toFixed(1)}%`,
    icon: '🎯'
  });

  const abandoned = state.orders.filter((order) => {
    if (order.status !== 'awaiting_payment') return false;
    const hours = (now - order.createdAt) / 36e5;
    return hours > 24;
  });
  result.abandoned = makeMetric('abandoned', 'Незавершённые заказы', abandoned.length, abandoned.length - 1, {
    icon: '⚠️'
  });

  const paidOrders = state.orders.filter((order) => order.paidAt);
  const avgMinutes = paidOrders.length
    ? paidOrders.reduce((acc, order) => acc + (order.paidAt - order.createdAt) / 60000, 0) / paidOrders.length
    : 0;
  result.timeToPay = makeMetric('timeToPay', 'Среднее время до оплаты', avgMinutes, avgMinutes + 5, {
    formatted: `${Math.round(avgMinutes)} мин`,
    icon: '⏱️'
  });

  const geoAggregation = aggregateBy(state.orders, (order) => order.geo).sort((a, b) => b.count - a.count);
  const topGeo = geoAggregation[0];
  const geoPercent = topGeo ? (topGeo.count / state.orders.length) * 100 : 0;
  result.topGeo = makeMetric('topGeo', 'Популярный GEO', geoPercent, geoPercent - 5, {
    formatted: topGeo ? `${state.countries[topGeo.key]?.flag || ''} ${state.countries[topGeo.key]?.name || topGeo.key}` : '—',
    subtitle: topGeo ? `${geoPercent.toFixed(1)}% заказов` : '',
    icon: '🌍'
  });

  const packageAggregation = aggregateBy(state.orders, (order) => order.packageType).sort((a, b) => b.count - a.count);
  const topPackage = packageAggregation[0];
  const packagePercent = topPackage ? (topPackage.count / state.orders.length) * 100 : 0;
  result.topPackage = makeMetric('topPackage', 'Популярный пакет', packagePercent, packagePercent - 4, {
    formatted: topPackage ? PACKAGE_LABELS[topPackage.key] : '—',
    subtitle: topPackage ? `${packagePercent.toFixed(1)}% заказов` : '',
    icon: '🧰'
  });

  return result;
}

function diffDays(range) {
  const diff = Math.round((range.to - range.from) / 86400000) + 1;
  return Math.max(diff, 1);
}

function aggregateBy(items, keyGetter) {
  const map = new Map();
  items.forEach((item) => {
    const key = keyGetter(item);
    const entry = map.get(key) || { key, count: 0, total: 0 };
    entry.count += 1;
    entry.total += item.priceEur;
    map.set(key, entry);
  });
  return [...map.values()];
}

function createMetricCards(metrics) {
  const groups = [
    ['totalRevenue', 'monthRevenue', 'averageCheck', 'ltv'],
    ['totalOrders', 'awaiting', 'paid', 'inProgress'],
    ['newToday', 'clientsTotal', 'repeat', 'conversion'],
    ['abandoned', 'timeToPay', 'topGeo', 'topPackage']
  ];

  const elements = [];
  groups.forEach((group) => {
    group.forEach((key) => {
      const metric = metrics[key];
      const card = document.createElement('article');
      card.className = 'metric-card';
      card.dataset.metric = key;
      card.addEventListener('click', () => openMetricDetail(metric));

      const header = document.createElement('div');
      header.className = 'metric-card__header';
      const title = document.createElement('div');
      title.className = 'metric-card__title';
      title.innerHTML = `${metric.icon || '📊'} ${metric.title}`;
      const delta = document.createElement('div');
      delta.className = `metric-card__delta is-${metric.trend}`;
      delta.innerHTML = `${metric.trend === 'up' ? '▲' : metric.trend === 'down' ? '▼' : '➖'} ${metric.delta}`;
      header.append(title, delta);

      const value = document.createElement('div');
      value.className = 'metric-card__value';
      value.textContent = metric.formatted || (typeof metric.value === 'number' ? numberFormatter.format(Math.round(metric.value)) : metric.value);

      const footer = document.createElement('div');
      footer.className = 'metric-card__footer';
      const subtitle = document.createElement('span');
      subtitle.textContent = metric.subtitle || 'vs пред. период';
      const prev = document.createElement('span');
      prev.textContent = metric.previousValue ? `Было: ${Math.round(metric.previousValue)}` : '';
      footer.append(subtitle, prev);

      card.append(header, value, footer);
      elements.push(card);
    });
  });
  return elements;
}

function openMetricDetail(metric) {
  const dialog = document.getElementById('order-modal');
  const container = document.getElementById('order-detail');
  container.innerHTML = `
    <div class="order-detail">
      <section class="order-section">
        <h4>${metric.icon || '📊'} ${metric.title}</h4>
        <p class="modal__text">Текущее значение: <strong>${metric.formatted || numberFormatter.format(Math.round(metric.value))}</strong></p>
        <p class="modal__text">Изменение: <strong>${metric.delta}</strong> (предыдущий период: ${metric.previousValue ? Math.round(metric.previousValue) : '—'})</p>
        <p class="modal__text">Детальная аналитика доступна в разделе отчётов. Вы можете экспортировать графики и отфильтровать заказы для уточнения.</p>
      </section>
    </div>`;
  dialog.showModal();
}
function renderCharts() {
  const periods = getChartPeriod();
  renderRevenueChart(periods);
  renderStatusChart();
  renderGeoChart();
  renderPackageChart();
}

function getChartPeriod() {
  if (state.metricsRange === 'custom' && state.metricsCustomRange) {
    return { from: state.metricsCustomRange.from, to: state.metricsCustomRange.to };
  }
  const to = new Date();
  const from = new Date();
  const range = state.metricsRange || Number(document.getElementById('chart-period').value) || 30;
  from.setDate(from.getDate() - range + 1);
  return { from, to };
}

function renderRevenueChart({ from, to }) {
  const days = [];
  const seriesMap = new Map();

  const cursor = new Date(from);
  while (cursor <= to) {
    const key = cursor.toISOString().slice(0, 10);
    days.push(key);
    seriesMap.set(key, { amount: 0, orders: 0 });
    cursor.setDate(cursor.getDate() + 1);
  }

  state.orders.forEach((order) => {
    if (!order.paidAt) return;
    if (order.paidAt < from || order.paidAt > to) return;
    const key = order.paidAt.toISOString().slice(0, 10);
    const entry = seriesMap.get(key);
    if (entry) {
      entry.amount += order.priceEur;
      entry.orders += 1;
    }
  });

  const labels = days.map((day) => day.slice(5).split('-').reverse().join('.'));
  const data = days.map((day) => seriesMap.get(day)?.amount ?? 0);

  const ctx = document.getElementById('revenue-chart');
  if (state.charts.revenue) state.charts.revenue.destroy();
  state.charts.revenue = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Доход, €',
          data,
          borderColor: '#8b5cf6',
          backgroundColor: 'rgba(139, 92, 246, 0.18)',
          fill: true,
          tension: 0.35,
          pointRadius: 4,
          pointHoverRadius: 6
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: {
          ticks: { color: 'rgba(226, 232, 240, 0.7)' },
          grid: { color: 'rgba(148, 163, 184, 0.08)' }
        },
        y: {
          ticks: { color: 'rgba(226, 232, 240, 0.7)' },
          grid: { color: 'rgba(148, 163, 184, 0.08)' }
        }
      },
      plugins: {
        legend: { labels: { color: 'rgba(226, 232, 240, 0.9)' } },
        tooltip: {
          callbacks: {
            label(context) {
              const dateKey = days[context.dataIndex];
              const entry = seriesMap.get(dateKey);
              return `Доход: ${currencyFormatter.format(context.parsed.y)} • Заказов: ${entry.orders}`;
            }
          }
        }
      }
    }
  });
}

function renderStatusChart() {
  const aggregation = aggregateBy(state.orders, (order) => order.status).map((item) => ({
    ...item,
    color: CHART_COLORS[item.key]
  }));
  const ctx = document.getElementById('status-chart');
  if (state.charts.status) state.charts.status.destroy();
  state.charts.status = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: aggregation.map((item) => STATUSES[item.key]?.label || item.key),
      datasets: [
        {
          data: aggregation.map((item) => item.count),
          backgroundColor: aggregation.map((item) => item.color),
          borderColor: '#0f172a'
        }
      ]
    },
    options: {
      onClick(event, elements) {
        if (!elements.length) return;
        const index = elements[0].index;
        const key = aggregation[index].key;
        state.filters.statuses = new Set([key]);
        buildStatusChips();
        renderOrders();
      },
      plugins: {
        legend: { labels: { color: 'rgba(226,232,240,0.9)' } },
        tooltip: {
          callbacks: {
            label(context) {
              const value = aggregation[context.dataIndex];
              const percent = (value.count / state.orders.length) * 100;
              return `${STATUSES[value.key].emoji} ${context.label}: ${value.count} (${percent.toFixed(1)}%)`;
            }
          }
        }
      }
    }
  });
}

function renderGeoChart() {
  const aggregation = aggregateBy(state.orders, (order) => order.geo)
    .map((item) => ({
      ...item,
      label: `${state.countries[item.key]?.flag || ''} ${state.countries[item.key]?.name || item.key}`
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);

  const ctx = document.getElementById('geo-chart');
  if (state.charts.geo) state.charts.geo.destroy();
  state.charts.geo = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: aggregation.map((item) => item.label),
      datasets: [
        {
          label: 'Количество заказов',
          data: aggregation.map((item) => item.count),
          backgroundColor: 'rgba(139, 92, 246, 0.6)'
        },
        {
          label: 'Доход, €',
          data: aggregation.map((item) => item.total),
          backgroundColor: 'rgba(59, 130, 246, 0.45)'
        }
      ]
    },
    options: {
      indexAxis: 'y',
      plugins: {
        legend: { labels: { color: 'rgba(226, 232, 240, 0.9)' } },
        tooltip: {
          callbacks: {
            label(context) {
              if (context.datasetIndex === 0) {
                return `Заказов: ${context.parsed.x}`;
              }
              return `Доход: ${currencyFormatter.format(context.parsed.x)}`;
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: 'rgba(226, 232, 240, 0.7)' }, grid: { color: 'rgba(148, 163, 184, 0.08)' } },
        y: { ticks: { color: 'rgba(226, 232, 240, 0.9)' }, grid: { display: false } }
      }
    }
  });
}

function renderPackageChart() {
  const aggregation = aggregateBy(state.orders, (order) => order.packageType);
  const ctx = document.getElementById('package-chart');
  if (state.charts.package) state.charts.package.destroy();
  state.charts.package = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: aggregation.map((item) => PACKAGE_LABELS[item.key]),
      datasets: [
        {
          data: aggregation.map((item) => item.count),
          backgroundColor: PACKAGE_COLORS
        }
      ]
    },
    options: {
      plugins: {
        legend: { labels: { color: 'rgba(226, 232, 240, 0.9)' } },
        tooltip: {
          callbacks: {
            label(context) {
              const item = aggregation[context.dataIndex];
              const percent = (item.count / state.orders.length) * 100;
              return `${context.label}: ${item.count} (${percent.toFixed(1)}%), Доход: ${currencyFormatter.format(item.total)}`;
            }
          }
        }
      }
    }
  });
}
function renderActivity() {
  const type = document.getElementById('activity-type').value;
  const query = document.getElementById('activity-search').value.toLowerCase();
  const list = document.getElementById('activity-feed');
  list.innerHTML = '';

  const filtered = state.activity
    .filter((item) => (type === 'all' ? true : item.eventType === type))
    .filter((item) => (query ? item.description.toLowerCase().includes(query) : true))
    .slice(0, 20);

  filtered.forEach((item) => {
    const li = document.createElement('li');
    li.className = 'activity__item';
    const card = document.createElement('div');
    card.className = 'activity-card';

    const header = document.createElement('div');
    header.className = 'activity-card__header';
    const meta = document.createElement('div');
    meta.className = 'activity-card__meta';
    const icon = EVENT_ICONS[item.eventType] || '📌';
    const time = item.createdAt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    meta.innerHTML = `<span>${icon}</span><span>${time}</span>`;

    const badge = document.createElement('span');
    badge.className = 'badge';
    badge.textContent = item.eventType;
    header.append(meta, badge);

    const description = document.createElement('p');
    description.textContent = item.description;

    const actions = document.createElement('div');
    actions.className = 'activity-card__actions';
    const orderBtn = document.createElement('button');
    orderBtn.className = 'btn btn--ghost';
    orderBtn.textContent = 'Открыть заказ';
    orderBtn.addEventListener('click', () => openOrderModal(item.orderId));
    actions.append(orderBtn);

    if (['awaiting_payment'].includes(item.metadata?.status) || item.eventType === 'order_created') {
      const remindBtn = document.createElement('button');
      remindBtn.className = 'btn btn--soft';
      remindBtn.textContent = 'Напомнить клиенту';
      remindBtn.addEventListener('click', () => showToast('📣', 'Напоминание отправлено (демо).'));
      actions.append(remindBtn);
    }

    const viewBtn = document.createElement('button');
    viewBtn.className = 'btn btn--ghost';
    viewBtn.textContent = 'Просмотреть';
    viewBtn.addEventListener('click', () => openOrderModal(item.orderId));
    actions.append(viewBtn);

    card.append(header, description, actions);
    li.appendChild(card);
    list.appendChild(li);
  });
}

function getFilteredOrders() {
  return state.orders.filter((order) => {
    if (!state.filters.statuses.has(order.status)) return false;
    if (state.filters.package !== 'all' && order.packageType !== state.filters.package) return false;
    if (state.filters.geo.size && !state.filters.geo.has(order.geo)) return false;
    if (state.filters.tester === 'none' && order.testerId !== null) return false;
    if (state.filters.tester !== 'none' && state.filters.tester !== 'all' && Number(state.filters.tester) !== Number(order.testerId)) return false;
    if (state.filters.amountFrom !== null && order.priceEur < state.filters.amountFrom) return false;
    if (state.filters.amountTo !== null && order.priceEur > state.filters.amountTo) return false;

    if (state.filters.query) {
      const haystack = [
        order.orderNumber,
        order.client.username || '',
        String(order.client.telegramId || ''),
        order.client.email || '',
        order.client.phone || ''
      ]
        .join(' ')
        .toLowerCase();
      if (!haystack.includes(state.filters.query.toLowerCase())) return false;
    }

    if (state.filters.period !== 'all' && state.filters.period !== 'custom') {
      const created = order.createdAt;
      const now = new Date();
      switch (state.filters.period) {
        case 'today': {
          const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
          if (created < today) return false;
          break;
        }
        case 'yesterday': {
          const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
          const yesterday = new Date(today);
          yesterday.setDate(today.getDate() - 1);
          if (!(created >= yesterday && created < today)) return false;
          break;
        }
        case '7': {
          const from = new Date(now);
          from.setDate(from.getDate() - 6);
          if (created < from) return false;
          break;
        }
        case '30': {
          const from = new Date(now);
          from.setDate(from.getDate() - 29);
          if (created < from) return false;
          break;
        }
        case 'month': {
          if (!(created.getMonth() === now.getMonth() && created.getFullYear() === now.getFullYear())) return false;
          break;
        }
        case 'prev_month': {
          const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
          if (!(created.getMonth() === prev.getMonth() && created.getFullYear() === prev.getFullYear())) return false;
          break;
        }
      }
    }

    if (state.filters.period === 'custom' && state.filters.from && state.filters.to) {
      const from = new Date(`${state.filters.from}T00:00:00`);
      const to = new Date(`${state.filters.to}T23:59:59`);
      if (order.createdAt < from || order.createdAt > to) return false;
    }

    return true;
  });
}

function sortOrders(orders) {
  const { key, direction } = state.sort;
  const multiplier = direction === 'asc' ? 1 : -1;
  return [...orders].sort((a, b) => {
    let aValue = a[key];
    let bValue = b[key];
    if (key === 'client') {
      aValue = (a.client.username || a.client.telegramId || '').toString();
      bValue = (b.client.username || b.client.telegramId || '').toString();
    }
    if (key === 'testerId') {
      aValue = a.testerId || 0;
      bValue = b.testerId || 0;
    }
    if (aValue === null || aValue === undefined) return 1 * multiplier;
    if (bValue === null || bValue === undefined) return -1 * multiplier;
    if (aValue instanceof Date && bValue instanceof Date) {
      return (aValue - bValue) * multiplier;
    }
    if (typeof aValue === 'string') {
      return aValue.localeCompare(bValue) * multiplier;
    }
    return (aValue - bValue) * multiplier;
  });
}

function getPagedOrders() {
  const filtered = sortOrders(getFilteredOrders());
  const total = filtered.length;
  const start = (state.page - 1) * state.pageSize;
  const items = filtered.slice(start, start + state.pageSize);
  return { items, total };
}
function renderOrders() {
  const tableBody = document.querySelector('#orders-table tbody');
  const { items, total } = getPagedOrders();
  tableBody.innerHTML = '';

  items.forEach((order) => {
    const row = document.createElement('tr');
    row.className = `${order.status} ${isOrderOverdue(order) ? 'overdue' : ''}`;
    row.dataset.id = order.id;

    const selectCell = document.createElement('td');
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.checked = state.selected.has(order.id);
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) state.selected.add(order.id);
      else state.selected.delete(order.id);
      renderSelected();
    });
    selectCell.appendChild(checkbox);

    const numberCell = document.createElement('td');
    const link = document.createElement('button');
    link.className = 'btn btn--ghost';
    link.textContent = order.orderNumber;
    link.addEventListener('click', (event) => {
      event.stopPropagation();
      openOrderModal(order.id);
    });
    numberCell.appendChild(link);

    const createdCell = document.createElement('td');
    createdCell.textContent = `${order.createdAt.toLocaleDateString('ru-RU')} ${order.createdAt.toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit'
    })}`;

    const clientCell = document.createElement('td');
    clientCell.innerHTML = `
      <strong>${order.client.username ? '@' + order.client.username : 'Нет username'}</strong><br />
      <span>${order.client.telegramId || '—'}</span>`;

    const packageCell = document.createElement('td');
    packageCell.innerHTML = `<span class="package-badge">${PACKAGE_LABELS[order.packageType]}</span>`;

    const geoCell = document.createElement('td');
    const geoInfo = state.countries[order.geo];
    geoCell.textContent = geoInfo ? `${geoInfo.flag} ${geoInfo.name}` : order.geo;

    const amountCell = document.createElement('td');
    amountCell.textContent = currencyFormatter.format(order.priceEur);

    const statusCell = document.createElement('td');
    statusCell.innerHTML = `<span class="order-status ${order.status}">${STATUSES[order.status].emoji} ${
      STATUSES[order.status].label
    }</span>`;

    const testerCell = document.createElement('td');
    if (order.testerId) {
      const tester = state.testers.find((tester) => tester.id === order.testerId);
      testerCell.textContent = tester ? tester.name : '—';
    } else {
      testerCell.textContent = 'Не назначен';
    }

    const actionsCell = document.createElement('td');
    actionsCell.appendChild(makeActionButton('👁️', 'Просмотр', () => openOrderModal(order.id)));
    actionsCell.appendChild(makeActionButton('📝', 'Заметка', () => openNoteModal(order.id)));
    const statusBtn = makeActionButton('▶️', 'Изменить статус', () => openStatusModal(order));
    actionsCell.appendChild(statusBtn);
    const moreButton = makeActionButton('⋮', 'Дополнительно', (event) => {
      event.stopPropagation();
      showMoreMenu(moreButton, order);
    });
    actionsCell.appendChild(moreButton);

    row.append(
      selectCell,
      numberCell,
      createdCell,
      clientCell,
      packageCell,
      geoCell,
      amountCell,
      statusCell,
      testerCell,
      actionsCell
    );

    row.addEventListener('click', (event) => {
      if (event.target.tagName === 'INPUT' || event.target.closest('button')) return;
      openOrderModal(order.id);
    });

    tableBody.appendChild(row);
  });

  renderSelected();
  renderPagination(total);
  const summary = document.getElementById('table-summary');
  const start = total ? (state.page - 1) * state.pageSize + 1 : 0;
  const end = Math.min(state.page * state.pageSize, total);
  summary.textContent = `Показано ${start}-${end} из ${total} заказов`;

  document.querySelectorAll('#orders-table thead th[data-sort]').forEach((th) => {
    if (th.dataset.listenerAttached) return;
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (state.sort.key === key) {
        state.sort.direction = state.sort.direction === 'asc' ? 'desc' : 'asc';
      } else {
        state.sort.key = key;
        state.sort.direction = 'asc';
      }
      renderOrders();
    });
    th.dataset.listenerAttached = 'true';
  });
}

function isOrderOverdue(order) {
  if (order.status !== 'awaiting_payment') return false;
  const hours = (new Date() - order.createdAt) / 36e5;
  return hours > 48;
}

function makeActionButton(icon, title, handler) {
  const button = document.createElement('button');
  button.className = 'btn-icon';
  button.textContent = icon;
  button.title = title;
  button.addEventListener('click', (event) => {
    event.stopPropagation();
    handler(event);
  });
  return button;
}

function showMoreMenu(button, order) {
  const menu = document.createElement('div');
  menu.className = 'context-menu';
  menu.style.position = 'absolute';
  menu.style.top = `${button.getBoundingClientRect().bottom + window.scrollY}px`;
  menu.style.left = `${button.getBoundingClientRect().left + window.scrollX}px`;
  menu.style.background = 'rgba(15, 23, 42, 0.95)';
  menu.style.border = '1px solid rgba(124, 58, 237, 0.4)';
  menu.style.borderRadius = '12px';
  menu.style.padding = '8px';
  menu.style.display = 'grid';
  menu.style.gap = '6px';
  menu.style.zIndex = 50;

  const items = [
    { label: '📋 Дублировать заказ', action: () => duplicateOrder(order) },
    { label: '💬 Написать клиенту', action: () => showToast('💬', 'Открыт чат с клиентом (демо).') },
    { label: '📄 Скачать отчёт', action: () => downloadReport(order) },
    { label: '🗑️ Удалить заказ', action: () => deleteOrder(order) }
  ];

  items.forEach((item) => {
    const btn = document.createElement('button');
    btn.className = 'btn btn--ghost';
    btn.textContent = item.label;
    btn.style.justifyContent = 'flex-start';
    btn.addEventListener('click', () => {
      item.action();
      if (document.body.contains(menu)) document.body.removeChild(menu);
    });
    menu.appendChild(btn);
  });

  const closeHandler = () => {
    if (document.body.contains(menu)) document.body.removeChild(menu);
    document.removeEventListener('click', closeHandler);
  };

  setTimeout(() => document.addEventListener('click', closeHandler), 0);
  document.body.appendChild(menu);
}
function duplicateOrder(order) {
  const newOrder = {
    ...order,
    id: Date.now(),
    orderNumber: `${order.orderNumber}-COPY`,
    createdAt: new Date(),
    status: 'awaiting_payment',
    paidAt: null,
    startedAt: null,
    completedAt: null
  };
  state.orders.unshift(newOrder);
  showToast('📋', `Создан дубликат ${newOrder.orderNumber}`);
  renderOrders();
  renderMetrics();
  renderCharts();
}

function downloadReport(order) {
  if (!order.reportUrl) {
    showToast('ℹ️', 'Отчёт ещё не загружен');
    return;
  }
  window.open(order.reportUrl, '_blank');
}

function deleteOrder(order) {
  if (confirm(`Удалить заказ ${order.orderNumber}?`)) {
    state.orders = state.orders.filter((item) => item.id !== order.id);
    state.selected.delete(order.id);
    renderAll();
    showToast('🗑️', `Заказ ${order.orderNumber} удалён (демо).`);
  }
}

function renderSelected() {
  const bulk = document.getElementById('bulk-actions');
  const count = state.selected.size;
  if (count) {
    bulk.hidden = false;
    document.getElementById('bulk-count').textContent = count;
  } else {
    bulk.hidden = true;
  }
  const pageOrders = getPagedOrders().items;
  const selectAll = document.getElementById('select-all');
  const allSelected = pageOrders.every((order) => state.selected.has(order.id)) && pageOrders.length > 0;
  selectAll.checked = allSelected;
}

function renderPagination(total) {
  const pages = Math.ceil(total / state.pageSize) || 1;
  const container = document.getElementById('pagination');
  container.innerHTML = '';

  const createButton = (label, page) => {
    const button = document.createElement('button');
    button.textContent = label;
    button.disabled = page < 1 || page > pages;
    if (page === state.page) button.classList.add('is-active');
    button.addEventListener('click', () => {
      if (page < 1 || page > pages) return;
      state.page = page;
      renderOrders();
    });
    return button;
  };

  container.appendChild(createButton('Назад', state.page - 1));
  for (let page = 1; page <= pages; page += 1) {
    container.appendChild(createButton(String(page), page));
  }
  container.appendChild(createButton('Вперёд', state.page + 1));
}

function openOrderModal(orderId) {
  const order = state.orders.find((item) => item.id === orderId);
  if (!order) {
    showToast('⚠️', 'Заказ не найден');
    return;
  }
  const tester = order.testerId ? state.testers.find((item) => item.id === order.testerId) : null;
  const dialog = document.getElementById('order-modal');
  const container = document.getElementById('order-detail');
  const country = state.countries[order.geo];

  const timeline = ['Создан', 'Оплачен', 'В работе', 'Завершён'];
  const timelineStatus = [
    true,
    Boolean(order.paidAt),
    Boolean(order.startedAt || order.status === 'completed'),
    Boolean(order.completedAt)
  ];

  container.innerHTML = `
    <div class="order-detail">
      <section class="order-section">
        <h4>Информация о клиенте</h4>
        <div class="order-grid">
          <div class="order-grid__item"><span>Username</span>${order.client.username ? '@' + order.client.username : '—'}</div>
          <div class="order-grid__item"><span>Telegram ID</span>${order.client.telegramId || '—'}</div>
          <div class="order-grid__item"><span>Email</span>${order.client.email || '—'}</div>
          <div class="order-grid__item"><span>Телефон</span>${order.client.phone || '—'}</div>
        </div>
      </section>
      <section class="order-section">
        <h4>Статус и прогресс</h4>
        <div class="order-status ${order.status}">${STATUSES[order.status].emoji} ${STATUSES[order.status].label}</div>
        <div class="progress">
          ${timeline
            .map((label, index) => `<div class="progress__step ${timelineStatus[index] ? 'progress__step--active' : ''}"><span>${label}</span></div>`)
            .join('')}
        </div>
        <button class="btn btn--primary" onclick="document.getElementById('status-modal').showModal()">Изменить статус</button>
      </section>
      <section class="order-section">
        <h4>Детали заказа</h4>
        <div class="order-grid">
          <div class="order-grid__item"><span>Пакет</span>${PACKAGE_LABELS[order.packageType]}</div>
          <div class="order-grid__item"><span>GEO</span>${country ? `${country.flag} ${country.name}` : order.geo}</div>
          <div class="order-grid__item"><span>Сумма</span>${currencyFormatter.format(order.priceEur)}</div>
          <div class="order-grid__item"><span>Метод оплаты</span>${order.paymentMethod}</div>
        </div>
        <div class="order-grid">
          <div class="order-grid__item"><span>Сайт</span>${
            order.websiteUrl
              ? `<a href="${order.websiteUrl}" target="_blank">${order.websiteUrl}</a>`
              : '—'
          }</div>
          <div class="order-grid__item"><span>Логин</span>${order.credentials?.login || '—'}</div>
          <div class="order-grid__item"><span>Пароль</span>${order.credentials?.password ? '••••••' : '—'}</div>
        </div>
        <p><span class="badge">Комментарий клиента</span><br />${order.comments || 'Нет комментариев'}</p>
      </section>
      <section class="order-section">
        <h4>Файлы от клиента (${order.attachments.length || 0})</h4>
        <div class="files-grid">
          ${order.attachments
            .map((file) => {
              if (file.type === 'image') {
                return `<div class="file-card"><img src="${file.url}" alt="${file.fileName}" /><div>${file.fileName}</div><div class="file-card__actions"><a class="btn btn--soft" href="${file.url}" target="_blank">Просмотр</a><a class="btn btn--ghost" href="${file.url}" download>Скачать</a></div></div>`;
              }
              if (file.type === 'video') {
                return `<div class="file-card"><video src="${file.url}" controls></video><div>${file.fileName}</div><div class="file-card__actions"><a class="btn btn--ghost" href="${file.url}" download>Скачать</a></div></div>`;
              }
              return `<div class="file-card"><div>${file.fileName}</div><div class="file-card__actions"><a class="btn btn--ghost" href="${file.url}" target="_blank">Открыть</a></div></div>`;
            })
            .join('') || '<p>Нет прикреплённых файлов</p>'}
        </div>
      </section>
      <section class="order-section">
        <h4>Подтверждение оплаты</h4>
        ${order.paymentProof
          ? `<p>✅ Чек получен ${new Date(order.paymentProof.uploadedAt).toLocaleString('ru-RU')} от ${order.paymentProof.admin || '—'}</p>
             <img src="${order.paymentProof.url}" alt="Чек оплаты" style="max-height:240px;border-radius:12px;object-fit:cover;" />`
          : `<p>⏳ Ожидается подтверждение оплаты.</p>`}
      </section>
      <section class="order-section">
        <h4>Назначение тестера</h4>
        ${
          tester
            ? `<div><strong>${tester.name}</strong> (${tester.geoFocus})</div><button class="btn btn--ghost" onclick="alert('Снять тестера (демо)')">Снять тестера</button>`
            : '<p>Тестер не назначен</p>'
        }
        <label class="input"><span>Выбрать тестера</span><select id="modal-tester">${state.testers
          .map((item) => `<option value="${item.id}" ${item.id === order.testerId ? 'selected' : ''}>${item.name}</option>`)
          .join('')}</select></label>
        <button class="btn btn--primary" onclick="alert('Назначить тестера (демо)')">Назначить тестера</button>
      </section>
    </div>`;

  dialog.showModal();
}
function openNoteModal(orderId) {
  const dialog = document.getElementById('note-modal');
  dialog.dataset.orderId = orderId;
  document.getElementById('note-text').value = '';
  dialog.showModal();
}

function openStatusModal(order) {
  const dialog = document.getElementById('status-modal');
  const text = document.getElementById('status-modal-text');
  text.textContent = `Текущий статус: ${STATUSES[order.status].label}`;
  dialog.dataset.orderId = order.id;
  dialog.showModal();
}

function exportOrdersToCsv(selectedIds) {
  const rows = (selectedIds?.length ? state.orders.filter((order) => selectedIds.includes(order.id)) : getFilteredOrders()).map(
    (order) => {
      const tester = order.testerId ? state.testers.find((item) => item.id === order.testerId)?.name || '' : '';
      return [
        order.orderNumber,
        order.createdAt.toISOString(),
        order.client.username || '',
        order.client.telegramId || '',
        PACKAGE_LABELS[order.packageType],
        order.geo,
        order.priceEur,
        order.status,
        tester,
        order.paidAt ? order.paidAt.toISOString() : '',
        order.startedAt ? order.startedAt.toISOString() : '',
        order.completedAt ? order.completedAt.toISOString() : '',
        order.reportUrl || '',
        order.websiteUrl || '',
        order.paymentMethod || '',
        order.comments?.replace(/\n/g, ' ')
      ];
    }
  );

  const header = [
    'Номер заказа',
    'Дата создания',
    'Username клиента',
    'Telegram ID клиента',
    'Пакет',
    'GEO',
    'Сумма',
    'Статус',
    'Имя тестера',
    'Дата оплаты',
    'Дата начала работы',
    'Дата завершения',
    'URL отчёта',
    'Сайт для теста',
    'Метод оплаты',
    'Комментарии клиента'
  ];

  const csvContent = [header, ...rows]
    .map((row) => row.map((value) => `"${String(value ?? '').replace(/"/g, '""')}"`).join(';'))
    .join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  const now = new Date();
  link.download = `orders_export_${now.toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
  link.click();
  URL.revokeObjectURL(url);
  showToast('⬇️', 'Экспорт завершён');
}

function exportActivity() {
  const type = document.getElementById('activity-type').value;
  const query = document.getElementById('activity-search').value.toLowerCase();
  const filtered = state.activity
    .filter((item) => (type === 'all' ? true : item.eventType === type))
    .filter((item) => (query ? item.description.toLowerCase().includes(query) : true));

  const header = ['Тип события', 'Описание', 'Дата'];
  const rows = filtered.map((item) => [item.eventType, item.description, item.createdAt.toISOString()]);
  const csv = [header, ...rows]
    .map((row) => row.map((value) => `"${String(value ?? '').replace(/"/g, '""')}"`).join(';'))
    .join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `activity_export_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.csv`;
  link.click();
  URL.revokeObjectURL(url);
  showToast('⬇️', 'Лента активности экспортирована');
}

function showToast(icon, text) {
  const container = document.getElementById('toast');
  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.innerHTML = `<span class="toast__icon">${icon}</span><span class="toast__text">${text}</span>`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('is-hiding');
    toast.style.opacity = '0';
    setTimeout(() => container.removeChild(toast), 400);
  }, 2500);
}

function downloadChart(chartId) {
  const chart = state.charts[chartId];
  if (!chart) {
    showToast('⚠️', 'График не найден');
    return;
  }
  const link = document.createElement('a');
  link.href = chart.toBase64Image('image/png', 1);
  link.download = `${chartId}_chart.png`;
  link.click();
  showToast('🖼️', 'Изображение графика сохранено');
}

function downloadDashboardSummary() {
  const metrics = calculateMetrics();
  const summary = Object.values(metrics)
    .map((metric) => `${metric.title}: ${metric.formatted || metric.value} (${metric.delta})`)
    .join('\n');
  const blob = new Blob([summary], { type: 'text/plain;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `dashboard_summary_${new Date().toISOString().slice(0, 10)}.txt`;
  link.click();
  URL.revokeObjectURL(url);
  showToast('📊', 'Экспорт дашборда выполнен');
}

function diffInMinutes(start, end) {
  return Math.round((end - start) / 60000);
}

document.addEventListener('DOMContentLoaded', init);
