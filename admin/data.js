const COUNTRY_INFO = {
  IN: { name: 'India', flag: '🇮🇳' },
  PK: { name: 'Pakistan', flag: '🇵🇰' },
  ID: { name: 'Indonesia', flag: '🇮🇩' },
  MY: { name: 'Malaysia', flag: '🇲🇾' },
  EG: { name: 'Egypt', flag: '🇪🇬' },
  CI: { name: 'Côte d\'Ivoire', flag: '🇨🇮' },
  UZ: { name: 'Uzbekistan', flag: '🇺🇿' },
  AZ: { name: 'Azerbaijan', flag: '🇦🇿' },
  KZ: { name: 'Kazakhstan', flag: '🇰🇿' },
  TH: { name: 'Thailand', flag: '🇹🇭' },
  AR: { name: 'Argentina', flag: '🇦🇷' },
  BR: { name: 'Brazil', flag: '🇧🇷' },
  BD: { name: 'Bangladesh', flag: '🇧🇩' },
  PH: { name: 'Philippines', flag: '🇵🇭' }
};

const TESTERS = [
  {
    id: 1,
    name: 'Anita Rao',
    geoFocus: 'IN',
    completed: 86,
    rating: 4.9,
    active: true,
    workload: 2,
    avatar: 'https://i.pravatar.cc/64?img=32'
  },
  {
    id: 2,
    name: 'Hendra Kusuma',
    geoFocus: 'ID',
    completed: 54,
    rating: 4.7,
    active: true,
    workload: 1,
    avatar: 'https://i.pravatar.cc/64?img=14'
  },
  {
    id: 3,
    name: 'Maria Lopes',
    geoFocus: 'BR',
    completed: 71,
    rating: 4.8,
    active: true,
    workload: 3,
    avatar: 'https://i.pravatar.cc/64?img=47'
  },
  {
    id: 4,
    name: 'Ahmed Elaraby',
    geoFocus: 'EG',
    completed: 42,
    rating: 4.5,
    active: true,
    workload: 1,
    avatar: 'https://i.pravatar.cc/64?img=58'
  },
  {
    id: 5,
    name: 'Aigerim Seidali',
    geoFocus: 'KZ',
    completed: 36,
    rating: 4.6,
    active: true,
    workload: 0,
    avatar: 'https://i.pravatar.cc/64?img=24'
  }
];

const SAMPLE_FILES = {
  receipt: {
    id: 'file_abc123',
    type: 'image',
    url: 'https://images.unsplash.com/photo-1521791136064-7986c2920216?auto=format&fit=crop&w=600&q=80',
    size: '1.2 MB',
    fileName: 'receipt.jpg',
    telegramLink: 'tg://openmessage?user_id=1001&message_id=9001'
  },
  document: {
    id: 'file_doc456',
    type: 'document',
    mime: 'application/pdf',
    url: 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf',
    size: '620 KB',
    fileName: 'integration-guide.pdf',
    telegramLink: 'tg://openmessage?user_id=1002&message_id=9002'
  },
  video: {
    id: 'file_video789',
    type: 'video',
    url: 'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4',
    size: '3.4 MB',
    duration: 42,
    preview: 'https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=400&q=80',
    fileName: 'walkthrough.mp4',
    telegramLink: 'tg://openmessage?user_id=1003&message_id=9003'
  }
};

const ORDERS = [
  {
    id: 101,
    orderNumber: 'QA-240401',
    createdAt: '2024-04-01T08:12:00Z',
    paidAt: '2024-04-01T09:10:00Z',
    startedAt: '2024-04-01T10:05:00Z',
    completedAt: '2024-04-02T12:45:00Z',
    client: {
      username: 'acme_ops',
      telegramId: 512345678,
      email: 'ops@acme.co',
      phone: '+91 99111 22334'
    },
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
    attachments: [SAMPLE_FILES.receipt, SAMPLE_FILES.document],
    paymentProof: { ...SAMPLE_FILES.receipt, uploadedAt: '2024-04-01T09:05:00Z', admin: 'Екатерина' },
    notes: 'Клиент просил ускорить.',
    siteReady: true
  },
  {
    id: 102,
    orderNumber: 'QA-240402',
    createdAt: '2024-04-01T11:20:00Z',
    paidAt: '2024-04-02T06:12:00Z',
    startedAt: '2024-04-02T08:00:00Z',
    completedAt: null,
    client: {
      username: 'payfast_id',
      telegramId: 612398744,
      email: 'cto@payfast.id'
    },
    packageType: 'mini',
    geo: 'ID',
    priceEur: 310,
    status: 'in_progress',
    testerId: 2,
    paymentMethod: 'GoPay',
    websiteUrl: 'https://dashboard.payfast.id',
    credentials: { login: 'audit', password: 'Audit#2024' },
    comments: 'Проверить fallback на QRIS.',
    reportUrl: null,
    attachments: [SAMPLE_FILES.receipt],
    paymentProof: { ...SAMPLE_FILES.receipt, uploadedAt: '2024-04-02T06:05:00Z', admin: 'Наталья' },
    notes: 'Требуется финальное видео.',
    siteReady: true
  },
  {
    id: 103,
    orderNumber: 'QA-240403',
    createdAt: '2024-04-02T07:48:00Z',
    paidAt: null,
    startedAt: null,
    completedAt: null,
    client: {
      username: null,
      telegramId: 712345680,
      phone: '+60 19 888 1122'
    },
    packageType: 'single',
    geo: 'MY',
    priceEur: 180,
    status: 'awaiting_payment',
    testerId: null,
    paymentMethod: 'GrabPay',
    websiteUrl: 'https://merchant.express.my/login',
    credentials: {},
    comments: 'Есть временные доступы, пришлют позже.',
    reportUrl: null,
    attachments: [],
    paymentProof: null,
    notes: 'Созвон с клиентом в 15:00.',
    siteReady: false
  },
  {
    id: 104,
    orderNumber: 'QA-240404',
    createdAt: '2024-03-29T13:22:00Z',
    paidAt: '2024-03-30T09:02:00Z',
    startedAt: '2024-03-30T11:17:00Z',
    completedAt: '2024-04-03T16:40:00Z',
    client: {
      username: 'crypto_uae',
      telegramId: 412236777,
      email: 'ceo@crypto-pay.me'
    },
    packageType: 'retainer',
    geo: 'EG',
    priceEur: 920,
    status: 'completed',
    testerId: 4,
    paymentMethod: 'Vodafone Cash',
    websiteUrl: 'https://merchant.crypto-pay.me',
    credentials: { login: 'merchant', password: 'CrYpto#908' },
    comments: 'Проверить on/off ramps.',
    reportUrl: 'https://example.com/reports/QA-240404.pdf',
    attachments: [SAMPLE_FILES.receipt, SAMPLE_FILES.video],
    paymentProof: { ...SAMPLE_FILES.receipt, uploadedAt: '2024-03-30T08:45:00Z', admin: 'Мария' },
    notes: '',
    siteReady: true
  },
  {
    id: 105,
    orderNumber: 'QA-240405',
    createdAt: '2024-04-03T05:32:00Z',
    paidAt: '2024-04-03T06:02:00Z',
    startedAt: null,
    completedAt: null,
    client: {
      username: 'swiftpay_bot',
      telegramId: 892344561,
      email: 'pm@swiftpay.co'
    },
    packageType: 'single',
    geo: 'PK',
    priceEur: 205,
    status: 'paid',
    testerId: null,
    paymentMethod: 'Easypaisa',
    websiteUrl: 'https://dashboard.swiftpay.pk',
    credentials: { login: 'qa', password: 'Test1234' },
    comments: 'Добавили новую карту.',
    reportUrl: null,
    attachments: [SAMPLE_FILES.receipt],
    paymentProof: { ...SAMPLE_FILES.receipt, uploadedAt: '2024-04-03T05:50:00Z', admin: 'Олег' },
    notes: 'Назначить тестера из PK.',
    siteReady: true
  },
  {
    id: 106,
    orderNumber: 'QA-240406',
    createdAt: '2024-03-25T17:18:00Z',
    paidAt: null,
    startedAt: null,
    completedAt: null,
    client: {
      username: 'latam_fin',
      telegramId: 978345612,
      email: 'ops@latamfin.ar'
    },
    packageType: 'mini',
    geo: 'AR',
    priceEur: 340,
    status: 'cancelled',
    testerId: null,
    paymentMethod: 'Mercado Pago',
    websiteUrl: 'https://latamfin.ar/login',
    credentials: {},
    comments: 'Перенесли запуск на май.',
    reportUrl: null,
    attachments: [],
    paymentProof: null,
    notes: 'Отменён по просьбе клиента.',
    siteReady: false
  },
  {
    id: 107,
    orderNumber: 'QA-240407',
    createdAt: '2024-04-04T08:55:00Z',
    paidAt: '2024-04-04T09:25:00Z',
    startedAt: '2024-04-04T11:30:00Z',
    completedAt: null,
    client: {
      username: 'uz_payments',
      telegramId: 623498711,
      phone: '+998 90 555 66 77'
    },
    packageType: 'single',
    geo: 'UZ',
    priceEur: 210,
    status: 'in_progress',
    testerId: 5,
    paymentMethod: 'Click',
    websiteUrl: 'https://merchant.pay.uz',
    credentials: { login: 'manager', password: 'UzPay#2024' },
    comments: 'Сделать скринкаст.',
    reportUrl: null,
    attachments: [SAMPLE_FILES.receipt],
    paymentProof: { ...SAMPLE_FILES.receipt, uploadedAt: '2024-04-04T09:10:00Z', admin: 'Алексей' },
    notes: '',
    siteReady: true
  },
  {
    id: 108,
    orderNumber: 'QA-240408',
    createdAt: '2024-04-04T12:48:00Z',
    paidAt: null,
    startedAt: null,
    completedAt: null,
    client: {
      username: 'thai_gateway',
      telegramId: 511287654
    },
    packageType: 'mini',
    geo: 'TH',
    priceEur: 320,
    status: 'awaiting_payment',
    testerId: null,
    paymentMethod: 'TrueMoney Wallet',
    websiteUrl: 'https://merchant.thgateway.com',
    credentials: {},
    comments: '',
    reportUrl: null,
    attachments: [],
    paymentProof: null,
    notes: 'Отправили повторный инвойс.',
    siteReady: false
  },
  {
    id: 109,
    orderNumber: 'QA-240409',
    createdAt: '2024-03-20T15:18:00Z',
    paidAt: '2024-03-20T16:01:00Z',
    startedAt: '2024-03-20T17:00:00Z',
    completedAt: '2024-03-21T18:45:00Z',
    client: {
      username: 'brazil_pay',
      telegramId: 411287654,
      email: 'ops@brazilpay.com'
    },
    packageType: 'retainer',
    geo: 'BR',
    priceEur: 980,
    status: 'completed',
    testerId: 3,
    paymentMethod: 'Pix',
    websiteUrl: 'https://brazilpay.com/dashboard',
    credentials: { login: 'qa', password: 'Pix#2024' },
    comments: '3 платежных сценария.',
    reportUrl: 'https://example.com/reports/QA-240409.pdf',
    attachments: [SAMPLE_FILES.document],
    paymentProof: { ...SAMPLE_FILES.receipt, uploadedAt: '2024-03-20T15:40:00Z', admin: 'Глеб' },
    notes: '',
    siteReady: true
  },
  {
    id: 110,
    orderNumber: 'QA-240410',
    createdAt: '2024-04-05T06:22:00Z',
    paidAt: null,
    startedAt: null,
    completedAt: null,
    client: {
      username: 'fintech_kz',
      telegramId: 733287111,
      email: 'ceo@fintech.kz'
    },
    packageType: 'single',
    geo: 'KZ',
    priceEur: 200,
    status: 'awaiting_payment',
    testerId: null,
    paymentMethod: 'Kaspi Pay',
    websiteUrl: 'https://fintech.kz',
    credentials: {},
    comments: 'Просит выделить тестера из KZ.',
    reportUrl: null,
    attachments: [],
    paymentProof: null,
    notes: '',
    siteReady: false
  },
  {
    id: 111,
    orderNumber: 'QA-240411',
    createdAt: '2024-03-27T04:50:00Z',
    paidAt: '2024-03-27T05:28:00Z',
    startedAt: '2024-03-27T07:15:00Z',
    completedAt: '2024-03-28T10:30:00Z',
    client: {
      username: 'egy_pay',
      telegramId: 444287987,
      email: 'support@egypay.eg'
    },
    packageType: 'mini',
    geo: 'EG',
    priceEur: 330,
    status: 'completed',
    testerId: 4,
    paymentMethod: 'Fawry',
    websiteUrl: 'https://merchants.egypay.eg',
    credentials: { login: 'audit', password: 'Egypt#2024' },
    comments: 'Добавили Apple Pay.',
    reportUrl: 'https://example.com/reports/QA-240411.pdf',
    attachments: [SAMPLE_FILES.document],
    paymentProof: { ...SAMPLE_FILES.receipt, uploadedAt: '2024-03-27T05:10:00Z', admin: 'Дарья' },
    notes: '',
    siteReady: true
  },
  {
    id: 112,
    orderNumber: 'QA-240412',
    createdAt: '2024-04-05T08:40:00Z',
    paidAt: '2024-04-05T09:10:00Z',
    startedAt: null,
    completedAt: null,
    client: {
      username: 'ph_payments',
      telegramId: 622334897
    },
    packageType: 'single',
    geo: 'PH',
    priceEur: 190,
    status: 'paid',
    testerId: null,
    paymentMethod: 'GCash',
    websiteUrl: 'https://merchant.phpayments.co',
    credentials: {},
    comments: 'Проверить OTP.',
    reportUrl: null,
    attachments: [SAMPLE_FILES.receipt],
    paymentProof: { ...SAMPLE_FILES.receipt, uploadedAt: '2024-04-05T08:55:00Z', admin: 'Антон' },
    notes: 'Попросили апдейт к 18:00.',
    siteReady: true
  }
];

const ACTIVITY_LOG = [
  {
    id: 2001,
    eventType: 'order_created',
    orderId: 112,
    userId: 622334897,
    description: 'Новый заказ QA-240412 от @ph_payments',
    createdAt: '2024-04-05T08:40:00Z',
    metadata: { status: 'awaiting_payment' }
  },
  {
    id: 2002,
    eventType: 'payment_proof_received',
    orderId: 112,
    userId: 622334897,
    description: 'Получен чек оплаты по QA-240412',
    createdAt: '2024-04-05T08:55:00Z',
    metadata: { fileId: 'file_abc123' }
  },
  {
    id: 2003,
    eventType: 'order_paid',
    orderId: 112,
    adminId: 902,
    description: 'Антон подтвердил оплату заказа QA-240412',
    createdAt: '2024-04-05T09:12:00Z',
    metadata: { status: 'paid' }
  },
  {
    id: 2004,
    eventType: 'tester_assigned',
    orderId: 107,
    testerId: 5,
    description: 'Назначен тестер Aigerim Seidali на QA-240407',
    createdAt: '2024-04-04T11:20:00Z',
    metadata: { testerId: 5 }
  },
  {
    id: 2005,
    eventType: 'status_changed',
    orderId: 107,
    adminId: 903,
    description: 'Статус QA-240407 изменён на in_progress',
    createdAt: '2024-04-04T11:30:00Z',
    metadata: { from: 'paid', to: 'in_progress' }
  },
  {
    id: 2006,
    eventType: 'note_added',
    orderId: 105,
    adminId: 901,
    description: 'Добавлена заметка по QA-240405: "Назначить тестера из PK"',
    createdAt: '2024-04-03T09:18:00Z'
  },
  {
    id: 2007,
    eventType: 'order_created',
    orderId: 108,
    description: 'Новый заказ QA-240408 от @thai_gateway',
    createdAt: '2024-04-04T12:48:00Z'
  },
  {
    id: 2008,
    eventType: 'order_created',
    orderId: 110,
    description: 'Новый заказ QA-240410 от @fintech_kz',
    createdAt: '2024-04-05T06:22:00Z'
  },
  {
    id: 2009,
    eventType: 'tester_created',
    testerId: 6,
    description: 'Добавлен тестер Omar Hassan (EG)',
    createdAt: '2024-04-02T14:15:00Z'
  },
  {
    id: 2010,
    eventType: 'report_uploaded',
    orderId: 104,
    testerId: 4,
    description: 'Отчёт по QA-240404 загружен тестером Ahmed Elaraby',
    createdAt: '2024-04-03T16:40:00Z',
    metadata: { reportUrl: 'https://example.com/reports/QA-240404.pdf' }
  },
  {
    id: 2011,
    eventType: 'admin_action',
    adminId: 903,
    description: 'Админ Алексей отправил напоминание по QA-240408',
    createdAt: '2024-04-04T18:25:00Z'
  },
  {
    id: 2012,
    eventType: 'order_completed',
    orderId: 104,
    testerId: 4,
    description: 'Заказ QA-240404 завершён',
    createdAt: '2024-04-03T16:45:00Z'
  },
  {
    id: 2013,
    eventType: 'order_cancelled',
    orderId: 106,
    adminId: 901,
    description: 'Отменён заказ QA-240406 по просьбе клиента',
    createdAt: '2024-03-26T09:30:00Z'
  },
  {
    id: 2014,
    eventType: 'tester_unassigned',
    orderId: 105,
    adminId: 903,
    description: 'Сняли тестера с QA-240405',
    createdAt: '2024-04-03T06:45:00Z'
  },
  {
    id: 2015,
    eventType: 'status_changed',
    orderId: 102,
    adminId: 904,
    description: 'QA-240402 переведён в статус in_progress',
    createdAt: '2024-04-02T08:00:00Z',
    metadata: { from: 'paid', to: 'in_progress' }
  },
  {
    id: 2016,
    eventType: 'order_paid',
    orderId: 101,
    adminId: 902,
    description: 'Подтверждение оплаты по QA-240401',
    createdAt: '2024-04-01T09:10:00Z'
  },
  {
    id: 2017,
    eventType: 'tester_assigned',
    orderId: 101,
    testerId: 1,
    description: 'Назначен тестер Anita Rao на QA-240401',
    createdAt: '2024-04-01T10:05:00Z'
  },
  {
    id: 2018,
    eventType: 'report_uploaded',
    orderId: 101,
    testerId: 1,
    description: 'Отчёт по QA-240401 загружен',
    createdAt: '2024-04-02T12:30:00Z',
    metadata: { reportUrl: 'https://example.com/reports/QA-240401.pdf' }
  },
  {
    id: 2019,
    eventType: 'order_completed',
    orderId: 101,
    testerId: 1,
    description: 'Заказ QA-240401 закрыт',
    createdAt: '2024-04-02T12:45:00Z'
  },
  {
    id: 2020,
    eventType: 'note_added',
    orderId: 103,
    adminId: 903,
    description: 'Напомнить клиенту о необходимости чека',
    createdAt: '2024-04-03T10:00:00Z'
  }
];

window.PaymentQA_DATA = {
  orders: ORDERS,
  testers: TESTERS,
  activity: ACTIVITY_LOG,
  countries: COUNTRY_INFO
};
