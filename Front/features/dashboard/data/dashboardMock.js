/**
 * Dashboard mock data — isolated from UI components.
 * Replace each export with a real API call when Laravel backend is ready.
 */

// ── Stats ────────────────────────────────────────────────────────────
export const STATS_ROW1 = [
  { key: 'activeProperties', value: '3,214',   change:  8, iconKey: 'Home',          iconBg: 'var(--color-brand-navy-light)' },
  { key: 'pendingRequests',  value: '47',       change: -5, iconKey: 'AlertTriangle',  iconBg: 'var(--color-warning-bg)' },
  { key: 'verifiedUsers',    value: '10,932',   change: 30, iconKey: 'CheckCircle2',   iconBg: 'var(--color-success-bg)' },
  { key: 'totalUsers',       value: '12,480',   change: 42, iconKey: 'Users',          iconBg: 'var(--color-brand-navy-light)' },
]

export const STATS_ROW2 = [
  { key: 'openIssues',     value: '9',      change: -30, iconKey: 'AlertCircle', iconBg: 'var(--color-danger-bg)' },
  { key: 'aiContracts',    value: '4,102',  change:  80, iconKey: 'Sparkles',    iconBg: 'var(--color-brand-gold-light)' },
  { key: 'monthlyRevenue', value: 2940000,  change:  13, iconKey: 'DollarSign',  iconBg: 'var(--color-success-bg)', isCurrency: true },
  { key: 'saasCurrent',    value: '1,879',  change:  65, iconKey: 'Activity',    iconBg: 'var(--color-brand-navy-light)' },
]

// ── Pipeline counts ──────────────────────────────────────────────────
export const PIPELINE_COUNTS = [312, 96, 58, 41, 55, 27, 1275, 912, 612, 14]

// ── Verify requests ──────────────────────────────────────────────────
export const getVerifyRequests = () => [
  { id: '#USR-88255', nameAr: 'خالد السبيعي',      nameEn: 'Khalid Al-Subaie',    typeAr: 'صورة هوية',     typeEn: 'ID Photo',        priority: 'normal', timeAr: 'منذ يومين',    timeEn: '2 days ago'  },
  { id: '#USR-88240', nameAr: 'منى الزهراني',       nameEn: 'Mona Al-Zahrani',     typeAr: 'صورة إقامة',    typeEn: 'Residence Photo', priority: 'normal', timeAr: 'منذ يوم واحد', timeEn: '1 day ago'   },
  { id: '#USR-88231', nameAr: 'عبدالله القحطاني', nameEn: 'Abdullah Al-Qahtani', typeAr: 'إثبات العنوان',  typeEn: 'Address Proof',   priority: 'high',   timeAr: 'منذ 3 ساعات',  timeEn: '3 hrs ago'   },
]

// ── Payments (amounts as numbers for formatCurrency) ─────────────────
export const PAYMENTS = [
  { id: 'C-447#', type: 'fee',  amount: 12400, currency: 'SAR', ok: true,  timeAr: 'منذ ساعة',    timeEn: '1 hr ago'  },
  { id: 'SUB#',   type: 'sub',  amount:  2900, currency: 'SAR', ok: true,  timeAr: 'منذ 3 ساعات', timeEn: '3 hrs ago' },
  { id: 'C-448#', type: 'fail', amount:     0, currency: 'SAR', ok: false, timeAr: 'منذ 5 ساعات', timeEn: '5 hrs ago' },
]

// ── System alerts ────────────────────────────────────────────────────
export const SYSTEM_ALERTS = [
  { icon: '⚠️', key: 'alert1', timeAr: 'منذ 4 دقائق', timeEn: '4 min ago', bad: true  },
  { icon: '🔒', key: 'alert2', timeAr: 'منذ ساعة',     timeEn: '1 hr ago',  bad: false },
  { icon: '✅', key: 'alert3', timeAr: 'منذ 5 ساعات',  timeEn: '5 hrs ago', bad: false },
]

// ── Audit log ────────────────────────────────────────────────────────
export const AUDIT_LOGS = [
  { initials: 'س', userAr: 'سارة الحربي',  userEn: 'Sara Al-Harbi',  actionKey: 'audit1Action', timeAr: 'منذ 7 دقائق',  timeEn: '7 min ago',  type: 'A' },
  { initials: 'ف', userAr: 'فهد المطري',   userEn: 'Fahad Al-Mutri', actionKey: 'audit2Action', timeAr: 'منذ 20 دقيقة', timeEn: '20 min ago', type: 'B' },
  { initials: 'ر', userAr: 'رفض',           userEn: 'Reject',         actionKey: 'audit3Action', timeAr: 'منذ ساعة',     timeEn: '1 hr ago',   type: 'X' },
]

// ── Users table ──────────────────────────────────────────────────────
export const USERS_LIST = [
  { init:'نع', initEn:'NE', nameAr:'نورة العتيبي',      nameEn:'Noura Al-Otaibi',     email:'noura@email.com',    roleKey:'rolePropOwner', statusVariant:'success', statusKey:'statusVerified', lastAr:'منذ ساعتين',  lastEn:'2 hrs ago'  },
  { init:'فم', initEn:'FM', nameAr:'فهد المطري',         nameEn:'Fahad Al-Mutri',       email:'fahad@email.com',    roleKey:'roleLawyer',    statusVariant:'navy',    statusKey:'statusActive',   lastAr:'منذ 4 دقائق', lastEn:'4 min ago'  },
  { init:'عف', initEn:'AF', nameAr:'عبدالله الفحطاني',  nameEn:'Abdullah Al-Fuhtani',  email:'abdallah@email.com', roleKey:'roleTenant',    statusVariant:'warning', statusKey:'statusReview',   lastAr:'منذ 4 ساعات', lastEn:'4 hrs ago'  },
  { init:'لح', initEn:'LH', nameAr:'لينا الحمدان',       nameEn:'Lina Al-Hamdan',       email:'lina@email.com',     roleKey:'roleBroker',    statusVariant:'danger',  statusKey:'statusRejected', lastAr:'منذ يومين',   lastEn:'2 days ago' },
]

// ── Risk contracts ───────────────────────────────────────────────────
export const RISK_CONTRACTS = [
  { ref:'RC-4488', lawyerAr:'أ. ريم القيس',    lawyerEn:'L. Reem Al-Qais',     statusVariant:'warning', statusKey:'statusLegalReview', risk: 8.4 },
  { ref:'RC-4471', lawyerAr:'أ. فهد المطري',   lawyerEn:'L. Fahad Al-Mutri',   statusVariant:'navy',    statusKey:'statusActive',       risk: 5.1 },
  { ref:'RC-4502', lawyerAr:'أ. سلمان الشيخ', lawyerEn:'L. Salman Al-Sheikh', statusVariant:'success', statusKey:'statusSigned',       risk: 1.9 },
]

// ── AI stats ─────────────────────────────────────────────────────────
export const AI_STATS = [
  { key: 'aiRiskScore',    value: '2.3/10' },
  { key: 'aiContractsGen', value: '4,102'  },
  { key: 'aiUptime',       value: '99.7%'  },
  { key: 'aiQueries',      value: '18.6K'  },
]

// ── Chart data — 12 months ───────────────────────────────────────────
const AR_MONTHS = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']
const EN_MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

const LINE_VALUES = [
  { verified: 540,  newU: 220 },
  { verified: 680,  newU: 310 },
  { verified: 820,  newU: 380 },
  { verified: 960,  newU: 490 },
  { verified: 1120, newU: 470 },
  { verified: 1280, newU: 610 },
  { verified: 1540, newU: 720 },
  { verified: 1810, newU: 760 },
  { verified: 2040, newU: 830 },
  { verified: 2210, newU: 910 },
  { verified: 2480, newU: 980 },
  { verified: 2750, newU: 1050 },
]

export const makeLineData = (t) =>
  AR_MONTHS.map((arM, i) => ({
    m: t.dir === 'rtl' ? arM : EN_MONTHS[i],
    verified: LINE_VALUES[i].verified,
    newU:     LINE_VALUES[i].newU,
  }))

export const makeBarData = (t) => [
  { m: t.dir==='rtl'?'يناير':'Jan',   r: 0.9  },
  { m: t.dir==='rtl'?'فبراير':'Feb',  r: 1.1  },
  { m: t.dir==='rtl'?'مارس':'Mar',    r: 1.2  },
  { m: t.dir==='rtl'?'أبريل':'Apr',   r: 1.5  },
  { m: t.dir==='rtl'?'مايو':'May',    r: 1.3  },
  { m: t.dir==='rtl'?'يونيو':'Jun',   r: 1.9  },
  { m: t.dir==='rtl'?'يوليو':'Jul',   r: 2.1  },
  { m: t.dir==='rtl'?'أغسطس':'Aug',   r: 1.8  },
  { m: t.dir==='rtl'?'سبتمبر':'Sep',  r: 2.3  },
  { m: t.dir==='rtl'?'أكتوبر':'Oct',  r: 2.5  },
  { m: t.dir==='rtl'?'نوفمبر':'Nov',  r: 2.7  },
  { m: t.dir==='rtl'?'ديسمبر':'Dec',  r: 2.94 },
]
