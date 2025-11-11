const COUNTRY_INFO = {
  IN: { name: 'India', flag: '🇮🇳' },
  PK: { name: 'Pakistan', flag: '🇵🇰' },
  ID: { name: 'Indonesia', flag: '🇮🇩' },
  MY: { name: 'Malaysia', flag: '🇲🇾' },
  EG: { name: 'Egypt', flag: '🇪🇬' },
  CI: { name: `Côte d'Ivoire`, flag: '🇨🇮' },
  UZ: { name: 'Uzbekistan', flag: '🇺🇿' },
  AZ: { name: 'Azerbaijan', flag: '🇦🇿' },
  KZ: { name: 'Kazakhstan', flag: '🇰🇿' },
  TH: { name: 'Thailand', flag: '🇹🇭' },
  AR: { name: 'Argentina', flag: '🇦🇷' },
  BR: { name: 'Brazil', flag: '🇧🇷' },
  MX: { name: 'Mexico', flag: '🇲🇽' },
  CO: { name: 'Colombia', flag: '🇨🇴' },
  VN: { name: 'Vietnam', flag: '🇻🇳' },
  TR: { name: 'Turkey', flag: '🇹🇷' },
  BD: { name: 'Bangladesh', flag: '🇧🇩' }
};

const TESTERS = [
  { id: 1, name: 'Anita Rao', geoFocus: 'IN', completed: 86, rating: 4.9, active: true, workload: 2 },
  { id: 2, name: 'Hendra Kusuma', geoFocus: 'ID', completed: 54, rating: 4.7, active: true, workload: 1 },
  { id: 3, name: 'Maria Lopes', geoFocus: 'BR', completed: 71, rating: 4.8, active: true, workload: 3 }
];

const FALLBACK_ORDERS = [
  {
    id: 1001,
    orderNumber: 'QA-240401',
    createdAt: '2024-04-01T08:12:00Z',
    paidAt: '2024-04-01T09:10:00Z',
    startedAt: '2024-04-01T10:05:00Z',
    completedAt: '2024-04-02T12:45:00Z',
    client: { username: 'acme_ops', telegramId: 512345678, email: 'ops@acme.co', phone: '+91 99111 22334' },
    packageType: 'single',
    geo: 'IN',
    priceEur: 220,
    status: 'completed',
    testerId: 1,
    paymentMethod: 'PhonePe',
    websiteUrl: 'https://pay.acme.in',
    credentials: { login: 'qa_admin', password: 'Sup3rSecret!' },
    comments: 'UPI flow failing on checkout.',
    reportUrl: 'https://example.com/reports/QA-240401.pdf',
    attachments: [],
    paymentProof: null,
    notes: '',
    siteReady: true,
    source: 'tg'
  },
  {
    id: 1002,
    orderNumber: 'QA-240402',
    createdAt: '2024-04-02T07:48:00Z',
    paidAt: null,
    startedAt: null,
    completedAt: null,
    client: { username: 'payfast_id', telegramId: 612398744, email: 'cto@payfast.id', phone: '' },
    packageType: 'mini',
    geo: 'ID',
    priceEur: 310,
    status: 'awaiting_payment',
    testerId: null,
    paymentMethod: 'GoPay',
    websiteUrl: 'https://dashboard.payfast.id',
    credentials: { login: 'audit', password: 'Audit#2024' },
    comments: 'Проверить fallback на QRIS.',
    reportUrl: null,
    attachments: [],
    paymentProof: null,
    notes: '',
    siteReady: true,
    source: 'site'
  }
];

function determinePackageType(testsCount) {
  if (!testsCount || testsCount <= 2) return 'single';
  if (testsCount <= 5) return 'mini';
  return 'retainer';
}

function buildActivity(orders) {
  return orders.map((order) => ({
    id: `order_${order.id}`,
    type: 'order_created',
    title: `Заказ #${order.orderNumber}`,
    user: order.client.username || order.client.telegramId || order.id,
    status: order.status,
    createdAt: order.createdAt,
    meta: {
      source: order.source,
      geo: order.geo
    }
  }));
}

function mapApiOrder(order) {
  const packageType = determinePackageType(order.testsCount || 1);
  return {
    id: order.id,
    orderNumber: `QA-${String(order.id).padStart(6, '0')}`,
    createdAt: order.createdAt,
    paidAt: order.status === 'paid' ? order.updatedAt : null,
    startedAt: null,
    completedAt: order.status === 'completed' ? order.updatedAt : null,
    client: {
      username: order.username || '',
      telegramId: order.userId,
      email: '',
      phone: ''
    },
    packageType,
    geo: order.geo,
    priceEur: order.priceEur || 0,
    status: order.status,
    testerId: null,
    paymentMethod: order.paymentMethod || '',
    websiteUrl: order.siteUrl || '',
    credentials: { login: order.login || '', password: order.password || '' },
    comments: order.comments || '',
    reportUrl: null,
    attachments: [],
    paymentProof: null,
    notes: '',
    siteReady: Boolean(order.siteUrl),
    source: order.source || 'tg',
    withdrawRequired: order.withdrawRequired,
    kycRequired: order.kycRequired,
    payoutOption: order.payoutOption,
    testsCount: order.testsCount || 1
  };
}

async function loadAdminData() {
  try {
    const response = await fetch('/api/orders', { headers: { Accept: 'application/json' } });
    if (!response.ok) {
      throw new Error(`API returned ${response.status}`);
    }
    const payload = await response.json();
    const apiOrders = Array.isArray(payload.orders) ? payload.orders.map(mapApiOrder) : [];
    const orders = apiOrders.length ? apiOrders : FALLBACK_ORDERS;
    return {
      orders,
      testers: TESTERS,
      activity: buildActivity(orders),
      countries: COUNTRY_INFO
    };
  } catch (error) {
    console.warn('Не удалось загрузить заказы из API, используется демо-данные', error);
    return {
      orders: FALLBACK_ORDERS,
      testers: TESTERS,
      activity: buildActivity(FALLBACK_ORDERS),
      countries: COUNTRY_INFO
    };
  }
}

window.PaymentQA_DATA_PROMISE = loadAdminData();
