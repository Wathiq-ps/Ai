'use client'

import { createContext, useContext, useState, useEffect } from 'react'

// ── Translations ──────────────────────────────────────────────────────────────
export const translations = {
  ar: {
    dir: 'rtl',
    lang: 'ar',

    // Common UI
    common: {
      openMenu:       'فتح القائمة',
      navigation:     'التنقل',
      sidebarNavigation: 'القائمة الجانبية',
      signOut:        'تسجيل الخروج',
      switchToEnglish:'التبديل إلى الإنجليزية',
      switchToArabic: 'التبديل إلى العربية',
      notifications:  'الإشعارات',
      userName:       'عبد الله أحمد',
      userRole:       'مسؤول أول',
      userInitial:    'س',
    },

    // Auth shared
    backToLogin:    'العودة إلى تسجيل الدخول',
    email:          'البريد الإلكتروني',
    emailPh:        'name@company.com',
    loading:        'جاري التحميل...',

    // Login
    loginTitle:     'تسجيل الدخول إلى لوحة التحكم',
    loginSub:       'أدخل بياناتك للمتابعة',
    continueBtn:    'متابعة',
    sendingOtp:     'جاري إرسال الرمز...',
    otpTitle:       'تحقق من بريدك الإلكتروني',
    otpSub:         'أدخل رمز التحقق المرسل إلى',
    otpLabel:       'رمز التحقق',
    verifyBtn:      'تحقق ودخول',
    verifyingOtp:   'جاري التحقق...',
    resendOtp:      'إعادة إرسال الرمز',
    changeEmail:    'تغيير البريد الإلكتروني',

    // Brand panel
    dashboardTitle: 'لوحة التحكم الإدارية',
    dashboardSub:   'تحكم كامل. رؤية واضحة. إدارة احترافية.',

    // Nav sidebar
    home:           'الرئيسية',
    verification:   'المراجعة والتحقق',
    identityCheck:  'التحقق من الهوية',
    propertyCheck:  'ملكية العقار',
    lawyerApproval: 'اعتماد المحامين',
    management:     'إدارة المنصة',
    users:          'المستخدمون',
    properties:     'العقارات',
    contracts:      'العقود',
    lawyers:        'المحامون',
    financial:      'العمليات المالية',
    knowledge:      'المعرفة والتحليلات',
    auditLogs:      'سجلات التدقيق',
    activities:     'النشاطات',
    verifyCenter:   'مركز التحقق',
    system:         'النظام',
    settings:       'الإعدادات',

    // Verification Center
    verificationCenter: {
      title:             'مركز التحقق',
      breadcrumb:        'مسار الصفحة',
      types:             'أنواع التحقق',
      description:       'إدارة ومراجعة طلبات التحقق المعلقة',
      searchPlaceholder: 'بحث برقم الطلب أو الاسم',
      filter:            'تصفية',
      viewDetails:       'عرض التفاصيل',
      pendingRequests:   'طلبًا بانتظار المراجعة',

      columns: {
        identity: {
          user:          'المستخدم',
          documentType:  'نوع الوثيقة',
          submittedAt:   'تاريخ التقديم',
          priority:      'الأولوية',
          status:        'الحالة',
        },
        property: {
          requestOwner:  'رقم الطلب / المالك',
          propertyType:  'نوع العقار',
          area:          'المساحة م²',
          city:          'المدينة',
          submittedAt:   'تاريخ التقديم',
          status:        'الحالة',
        },
        lawyers: {
          lawyer:        'المحامي',
          licenseNumber: 'رقم الترخيص',
          submittedAt:   'تاريخ التقديم',
          specialty:     'التخصص',
          status:        'الحالة',
        },
      },

      documentTypes: {
        nationalId:     'هوية وطنية',
        passport:       'جواز سفر',
        residenceCard:  'بطاقة إقامة',
      },

      propertyTypes: {
        residential:    'سكني',
        commercial:     'تجاري',
      },

      specialties: {
        realEstate:     'العقارات',
        contractNotary: 'توثيق العقود',
      },

      priorities: {
        high:           'عالية',
        medium:         'متوسطة',
        low:            'منخفضة',
      },

      statuses: {
        pending:        'قيد المراجعة',
        approved:       'موثّق',
        rejected:       'مرفوض',
      },
    },

    // Dashboard stats
    activeProperties: 'عقارات نشطة',
    pendingRequests:  'طلبات تحقق معلقة',
    verifiedUsers:    'مستخدمون مؤتمنون',
    totalUsers:       'المستخدمون',
    openIssues:       'مشاكل مفتوحة',
    aiContracts:      'عقود فنشأة بالذكاء الاصطناعي',
    monthlyRevenue:   'الإيرادات الشهرية',
    saasCurrent:      'جارية',

    // Top bar
    searchPh:         'بحث: عقد، عقار، رقم مرجعي...',

    // Dashboard — Welcome
    welcomeUser:      'مرحباً، أدمن 👋',
    welcomeDate:      'الإثنين ١٢ أغسطس ٢٠٢٦',

    // Dashboard — Priority Center
    priorityCenter:   'مركز التحقق — أولوية اليوم',
    prioritySub:      'راجع طلبات التحقق قبل انتهاء المهلة الزمنية المحددة',
    avgReviewTime:    'متوسط وقت المراجعة',
    highPriority:     'أولوية عالية',
    totalPending:     'إجمالي المعلق',

    // Dashboard — Verify section
    verifyTitle:      'التحقق من الهوية',
    verifyTabProperty:'ملكية العقار',
    verifyTabLawyer:  'اعتماد المحامين',
    verifyShowAll:    'عرض جميع طلبات التحقق',
    highPriorityBadge:'أولوية عالية',
    rejectBtn:        '✕ رفض',
    approveBtn:       '✓ اعتماد سريع',

    // Dashboard — Contract pipeline
    contractLife:     'حياة العقد',
    contractSub:      'العقود النشطة عبر مراحل سير العمل',
    viewAllContracts: 'عرض جميع العقود',
    pipeline: ['سودة','مراجعة الذكاء الاصطناعي','مراجعة المحامي','معتمد','بانتظار التوقيع','موقع','بانتظار الدفع','نشط','مكتمل','ملغى'],

    // Dashboard — Charts
    userGrowth:       'نمو المستخدمين',
    last12Months:     'آخر ١٢ شهر',
    revenueTitle:     'اتجاه الإيرادات',
    last6Months:      'آخر ٦ أشهر',
    chartVerified:    'مؤتمنون',
    chartNew:         'جدد',
    chartRevenue:     'إيرادات',

    // Dashboard — AI Monitor
    aiMonitorTitle:   'مراقبة الذكاء الاصطناعي',
    aiMonitorSub:     'حالة النظام والمعرفة القانونية (RAG)',
    aiRiskScore:      'متوسط درجة الخطورة',
    aiContractsGen:   'عقود فنشأة بـ AI',
    aiUptime:         'وقت تشغيل النظام',
    aiQueries:        'استفسارات هذا الشهر',
    aiKbHealth:       'سلامة قاعدة المعرفة القانونية',

    // Dashboard — Donut
    contractDist:     'توزيع حالات العقود',
    donutActive:      'نشط',
    donutLegal:       'مراجعة قانونية',
    donutPending:     'بانتظار التوقيع',
    donutDone:        'مكتمل',

    // Dashboard — Payments
    paymentsTitle:    'مدفوعات حديثة',
    paymentFee:       'دفعة عمولة',
    paymentSub:       'مكتب الراشد',
    paymentFail:      'فشل الدفع',

    // Dashboard — System alerts
    alertsTitle:      'تنبيهات النظام',
    alert1:           'ارتفاع في وقت استجابة الذكاء الاصطناعي',
    alert2:           'صيانة مجدولة للنظام — الأحد ٣٠',
    alert3:           'تم تحديث قاعدة المعرفة القانونية بنجاح',

    // Dashboard — Audit logs
    auditTitle:       'أحداث التدقيق',
    audit1Action:     'اعتمدت هوية #USR-88190',
    audit2Action:     'تعديل صلاحيات محامي — أ. فهد',
    audit3Action:     'رفض طلب ملكية عقار #PR-2201',

    // Dashboard — Users table
    usersTitle:       'المستخدمون',
    usersSubtitle:    'إدارة حسابات المستخدمين وأدوارهم',
    addUser:          ' إضافة مستخدم',
    searchUsers:      'بحث بالاسم أو البريد أو الرقم',
    filterStatus:     'الحالة',
    filterRole:       'الدور',
    filterAll:        'الكل',
    advancedFilter:   'تصفية متقدمة',
    bulkActions:      'إجراءات جماعية',
    colUser:          'المستخدم',
    colRole:          'الدور',
    colStatus:        'الحالة',
    colLastActive:    'آخر نشاط',
    showAll:          'عرض الكل',

    // User roles & statuses
    rolePropOwner:    'مالك عقار',
    roleLawyer:       'محامي',
    roleTenant:       'مستأجر',
    roleBroker:       'وسيط عقاري',
    statusVerified:   'مؤتمن',
    statusActive:     'نشط',
    statusReview:     'قيد المراجعة',
    statusRejected:   'مرفوض',

    // Dashboard — Risk contracts
    riskTitle:        'عقود ذات مخاطرة مرتفعة',
    riskSub:          'عقود تتطلب مراجعة قانونية فورية بناء على تحليل الذكاء الاصطناعي',
    colContract:      'رقم العقد',
    colLawyer:        'المحامي المسؤول',
    colRisk:          'درجة المخاطرة',
    statusLegalReview:'مراجعة قانونية',
    statusSigned:     'موقع',
    viewAll:          'عرض الكل',
  },

  en: {
    dir: 'ltr',
    lang: 'en',

    // Common UI
    common: {
      openMenu:       'Open menu',
      navigation:     'Navigation',
      sidebarNavigation: 'Sidebar navigation',
      signOut:        'Sign out',
      switchToEnglish:'Switch to English',
      switchToArabic: 'Switch to Arabic',
      notifications:  'Notifications',
      userName:       'Abdullah Ahmed',
      userRole:       'Senior Admin',
      userInitial:    'S',
    },

    // Auth shared
    backToLogin:    'Back to Login',
    email:          'Email',
    emailPh:        'name@company.com',
    loading:        'Loading...',

    // Login
    loginTitle:     'Sign in to Dashboard',
    loginSub:       'Enter your credentials to continue',
    continueBtn:    'Continue',
    sendingOtp:     'Sending code...',
    otpTitle:       'Verify your email',
    otpSub:         'Enter the verification code sent to',
    otpLabel:       'Verification code',
    verifyBtn:      'Verify & Sign In',
    verifyingOtp:   'Verifying...',
    resendOtp:      'Resend code',
    changeEmail:    'Change email',

    // Brand panel
    dashboardTitle: 'Admin Dashboard',
    dashboardSub:   'Full control. Clear vision. Professional management.',

    // Nav sidebar
    home:           'Home',
    verification:   'Review & Verification',
    identityCheck:  'Identity Check',
    propertyCheck:  'Property Ownership',
    lawyerApproval: 'Lawyer Approval',
    management:     'Platform Management',
    users:          'Users',
    properties:     'Properties',
    contracts:      'Contracts',
    lawyers:        'Lawyers',
    financial:      'Financial Ops',
    knowledge:      'Knowledge & Analytics',
    auditLogs:      'Audit Logs',
    activities:     'Activities',
    verifyCenter:   'Verify Center',
    system:         'System',
    settings:       'Settings',

    // Verification Center
    verificationCenter: {
      title:             'Verification Center',
      breadcrumb:        'Breadcrumb',
      types:             'Verification types',
      description:       'Manage and review pending verification requests',
      searchPlaceholder: 'Search by request ID or name',
      filter:            'Filter',
      viewDetails:       'View details',
      pendingRequests:   'requests pending review',

      columns: {
        identity: {
          user:          'User',
          documentType:  'Document type',
          submittedAt:   'Submitted date',
          priority:      'Priority',
          status:        'Status',
        },
        property: {
          requestOwner:  'Request ID / Owner',
          propertyType:  'Property type',
          area:          'Area m²',
          city:          'City',
          submittedAt:   'Submitted date',
          status:        'Status',
        },
        lawyers: {
          lawyer:        'Lawyer',
          licenseNumber: 'License number',
          submittedAt:   'Submitted date',
          specialty:     'Specialty',
          status:        'Status',
        },
      },

      documentTypes: {
        nationalId:     'National ID',
        passport:       'Passport',
        residenceCard:  'Residence card',
      },

      propertyTypes: {
        residential:    'Residential',
        commercial:     'Commercial',
      },

      specialties: {
        realEstate:     'Real estate',
        contractNotary: 'Contract notarization',
      },

      priorities: {
        high:           'High',
        medium:         'Medium',
        low:            'Low',
      },

      statuses: {
        pending:        'Under review',
        approved:       'Verified',
        rejected:       'Rejected',
      },
    },

    // Dashboard stats
    activeProperties: 'Active Properties',
    pendingRequests:  'Pending Verification',
    verifiedUsers:    'Verified Users',
    totalUsers:       'Users',
    openIssues:       'Open Issues',
    aiContracts:      'AI-Generated Contracts',
    monthlyRevenue:   'Monthly Revenue',
    saasCurrent:      'Current',

    // Top bar
    searchPh:         'Search: contract, property, ref number...',

    // Dashboard — Welcome
    welcomeUser:      'Welcome, Admin 👋',
    welcomeDate:      'Monday, August 12, 2026',

    // Dashboard — Priority Center
    priorityCenter:   'Verification Center — Today\'s Priority',
    prioritySub:      'Review verification requests before the deadline expires',
    avgReviewTime:    'Avg Review Time',
    highPriority:     'High Priority',
    totalPending:     'Total Pending',

    // Dashboard — Verify section
    verifyTitle:      'Identity Verification',
    verifyTabProperty:'Property Ownership',
    verifyTabLawyer:  'Lawyer Approval',
    verifyShowAll:    'View all verification requests',
    highPriorityBadge:'High Priority',
    rejectBtn:        '✕ Reject',
    approveBtn:       '✓ Quick Approve',

    // Dashboard — Contract pipeline
    contractLife:     'Contract Lifecycle',
    contractSub:      'Active contracts across workflow stages',
    viewAllContracts: 'View all contracts',
    pipeline: ['Draft','AI Review','Lawyer Review','Approved','Awaiting Signature','Signed','Awaiting Payment','Active','Completed','Cancelled'],

    // Dashboard — Charts
    userGrowth:       'User Growth',
    last12Months:     'Last 12 months',
    revenueTitle:     'Revenue Trend',
    last6Months:      'Last 6 months',
    chartVerified:    'Verified',
    chartNew:         'New',
    chartRevenue:     'Revenue',

    // Dashboard — AI Monitor
    aiMonitorTitle:   'AI Monitor',
    aiMonitorSub:     'System status & legal knowledge base (RAG)',
    aiRiskScore:      'Avg Risk Score',
    aiContractsGen:   'AI-Generated Contracts',
    aiUptime:         'System Uptime',
    aiQueries:        'Queries This Month',
    aiKbHealth:       'Legal Knowledge Base Health',

    // Dashboard — Donut
    contractDist:     'Contract Status Distribution',
    donutActive:      'Active',
    donutLegal:       'Legal Review',
    donutPending:     'Awaiting Signature',
    donutDone:        'Completed',

    // Dashboard — Payments
    paymentsTitle:    'Recent Payments',
    paymentFee:       'Commission Payment',
    paymentSub:       'Al-Rashed Office',
    paymentFail:      'Payment Failed',

    // Dashboard — System alerts
    alertsTitle:      'System Alerts',
    alert1:           'AI response time spike detected',
    alert2:           'Scheduled maintenance — Sunday 30th',
    alert3:           'Legal knowledge base updated successfully',

    // Dashboard — Audit logs
    auditTitle:       'Audit Events',
    audit1Action:     'Approved identity #USR-88190',
    audit2Action:     'Updated lawyer permissions — A. Fahad',
    audit3Action:     'Rejected property ownership #PR-2201',

    // Dashboard — Users table
    usersTitle:       'Users',
    usersSubtitle:    'Manage user accounts and roles',
    addUser:          ' Add User',
    searchUsers:      'Search by name, email or ID',
    filterStatus:     'Status',
    filterRole:       'Role',
    filterAll:        'All',
    advancedFilter:   'Advanced Filter',
    bulkActions:      'Bulk Actions',
    colUser:          'User',
    colRole:          'Role',
    colStatus:        'Status',
    colLastActive:    'Last Active',
    showAll:          'View All',

    // User roles & statuses
    rolePropOwner:    'Property Owner',
    roleLawyer:       'Lawyer',
    roleTenant:       'Tenant',
    roleBroker:       'Real Estate Broker',
    statusVerified:   'Verified',
    statusActive:     'Active',
    statusReview:     'Under Review',
    statusRejected:   'Rejected',

    // Dashboard — Risk contracts
    riskTitle:        'High-Risk Contracts',
    riskSub:          'Contracts requiring immediate legal review based on AI analysis',
    colContract:      'Contract No.',
    colLawyer:        'Responsible Lawyer',
    colRisk:          'Risk Score',
    statusLegalReview:'Legal Review',
    statusSigned:     'Signed',
    viewAll:          'View All',
  },
}

// ── Context ───────────────────────────────────────────────────────────────────
const LanguageContext = createContext(null)

export function LanguageProvider({ children }) {
  const [locale, setLocale] = useState('ar')

  const t = translations[locale]
  const toggleLanguage = () => setLocale((l) => (l === 'ar' ? 'en' : 'ar'))

  // ✅ KEY FIX: set dir and lang directly on <html> so CSS selectors like
  // [dir="rtl"] .sidebar and [dir="ltr"] .sidebar work correctly from any
  // depth in the tree — not just children of the inner <div>.
  useEffect(() => {
    document.documentElement.setAttribute('dir',  t.dir)
    document.documentElement.setAttribute('lang', t.lang)
  }, [t.dir, t.lang])

  return (
    <LanguageContext.Provider value={{ locale, t, toggleLanguage }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLang() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLang must be used inside LanguageProvider')
  return ctx
}