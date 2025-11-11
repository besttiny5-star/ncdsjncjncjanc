(() => {
  const API_PREFIX = '/api';

  async function fetchJson(path, options = {}) {
    const response = await fetch(`${API_PREFIX}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Request failed with status ${response.status}`);
    }
    return response.json();
  }

  async function loadPaymentQaData() {
    const dashboard = await fetchJson('/dashboard');
    return dashboard;
  }

  async function updateOrderStatus(orderId, payload) {
    return fetchJson(`/orders/${orderId}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  }

  window.PaymentQA = {
    loadData: loadPaymentQaData,
    updateOrderStatus,
    fetchJson,
  };
})();
