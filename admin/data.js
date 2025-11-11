(() => {
  const DASHBOARD_ENDPOINT = '/api/dashboard';

  const PaymentQA = {
    data: null,
    loading: false,
    lastError: null,
    lastUpdated: null,
    _ready: false,
    _pending: null,
    async refresh() {
      if (this._pending) {
        return this._pending;
      }

      this.loading = true;
      const request = fetch(DASHBOARD_ENDPOINT, {
        headers: { Accept: 'application/json' },
        credentials: 'same-origin'
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Failed to load dashboard: ${response.status}`);
          }
          return response.json();
        })
        .then((payload) => {
          const normalized = normalizeDashboardData(payload);
          this.data = normalized;
          this.lastError = null;
          this.lastUpdated = new Date();
          const eventName = this._ready ? 'paymentqa:data-updated' : 'paymentqa:data-ready';
          this._ready = true;
          window.dispatchEvent(new CustomEvent(eventName, { detail: normalized }));
          return normalized;
        })
        .catch((error) => {
          this.lastError = error;
          console.error('[PaymentQA] Не удалось загрузить данные панели', error);
          throw error;
        })
        .finally(() => {
          this.loading = false;
          this._pending = null;
        });

      this._pending = request;
      return request;
    }
  };

  function normalizeDashboardData(raw) {
    const toDate = (value) => (value ? new Date(value) : null);
    const normalizeOrder = (order) => {
      if (!order) return null;
      const attachments = Array.isArray(order.attachments) ? order.attachments : [];
      const paymentProof = order.paymentProof
        ? {
            ...order.paymentProof,
            uploadedAt: toDate(order.paymentProof.uploadedAt)
          }
        : null;
      return {
        ...order,
        createdAt: toDate(order.createdAt),
        paidAt: toDate(order.paidAt),
        startedAt: toDate(order.startedAt),
        completedAt: toDate(order.completedAt),
        attachments,
        paymentProof
      };
    };

    const normalizeActivity = (item) => ({
      ...item,
      createdAt: toDate(item.createdAt)
    });

    return {
      orders: Array.isArray(raw?.orders) ? raw.orders.map(normalizeOrder).filter(Boolean) : [],
      testers: Array.isArray(raw?.testers) ? raw.testers : [],
      activity: Array.isArray(raw?.activity) ? raw.activity.map(normalizeActivity) : [],
      countries: raw?.countries || {}
    };
  }

  Object.defineProperty(PaymentQA, 'ready', {
    enumerable: true,
    get() {
      return this._ready;
    }
  });

  window.PaymentQA = PaymentQA;

  PaymentQA.refresh().catch(() => {
    /* ошибки уже залогированы */
  });
})();
