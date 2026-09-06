# WATHIQ Frontend — Phase 1

This document reflects the current Phase 1 source tree. The project is intentionally API-ready, but dashboard data remains isolated mock data until the Backend API contract is delivered.

```text
Wathiq/
├── app/
│   ├── layout.js                         # Root metadata + global CSS
│   ├── page.js                           # Entry redirect
│   ├── globals.css                       # Tailwind v4 + canonical design tokens
│   ├── icon.svg                          # Browser tab icon
│   │
│   ├── (auth)/                           # Authentication routes
│   │   ├── layout.js
│   │   ├── login/page.js                 # Email → OTP request
│   │   └── verify-otp/page.js            # OTP verification
│   │
│   ├── (dashboard)/                      # Protected admin UI
│   │   ├── layout.js                     # Sidebar + TopBar + AdminGuard
│   │   └── dashboard/page.js             # Phase 1 dashboard composition
│   │
│   └── api/auth/                         # Server-side auth boundary / proxy
│       ├── otp/request/route.js
│       ├── otp/verify/route.js
│       ├── refresh/route.js
│       ├── logout/route.js
│       └── session/route.js
│
├── components/
│   ├── auth/AuthLayout.jsx
│   ├── dashboard/                        # Dashboard shell + reusable sections
│   │   ├── AdminGuard.jsx
│   │   ├── Sidebar.jsx
│   │   ├── TopBar.jsx
│   │   ├── StatCard.jsx
│   │   └── sections/
│   └── ui/                               # Shared UI primitives
│       ├── Badge.jsx
│       ├── Button.jsx
│       ├── Card.jsx
│       ├── Input.jsx
│       ├── SectionHeader.jsx
│       ├── Spinner.jsx
│       ├── Text.jsx
│       └── WathiqLogo.jsx
│
├── config/                               # Country / currency / locale configuration
├── context/                              # Language + sidebar state
├── features/auth/                       # Auth domain logic
│   ├── hooks/useAdminGuard.js
│   └── services/authService.js           # Frontend auth API contract boundary
├── features/dashboard/                  # Dashboard domain
│   └── data/dashboardMock.js             # Phase 1 mock data only
├── lib/
│   ├── api/server.js                     # Server-only backend client
│   ├── auth/                             # Auth constants + development preview
│   ├── colors.js                         # CSS-variable bridge for JS-only libraries
│   └── utils.js
├── public/                               # Official WATHIQ logo assets
├── proxy.js                              # Early protected-route gate
├── .env.example                          # Safe environment template
└── .env.local                            # Local-only environment values (ignored by Git)
```

## Architecture rules

### Design System
The canonical design tokens live in `app/globals.css` under Tailwind v4 `@theme`. `lib/colors.js` contains only CSS-variable references for libraries that require JavaScript values; raw brand hex values should not be introduced into components.

Official WATHIQ brand tokens:
- Primary / Azul Brant: `#002366`
- Secondary / Periwinkle Soft: `#B5C4FF`
- Accent / Corporate Gold: `#FABD00`
- White: `#FFFFFF`
- Font family: Alexandria
- Headline XL: 700 / 48px
- Headline LG: 700 / 32px
- Body LG: 400 / 18px
- Label MD: 600 / 14px

The existing Phase 1 screen sizes are intentionally preserved; the official typography scale is available as design tokens for new screens.

### Reusability
Shared visual patterns belong in `components/ui`. Dashboard-specific repeated patterns belong in `components/dashboard` or `components/dashboard/sections`. Pages compose components rather than duplicating their internal UI.

### API boundary
The UI does not call Laravel directly. Authentication requests go through `app/api/auth/*`, while `features/auth/services/authService.js` is the client-facing service boundary. When dashboard APIs arrive, keep their calls in a feature service/hook layer and pass normalized data into presentational components.

Do not place `fetch()` calls inside dashboard section components.

### Mock data
`features/dashboard/data/dashboardMock.js` is temporary Phase 1 data. When the Backend contract is ready, replace the data source at the feature/service boundary without rebuilding the visual components.

### Security
`proxy.js` provides early route protection and `AdminGuard` verifies the current authenticated user/role. These are frontend protections for navigation/UX. Backend authorization must remain the real security boundary for every protected API.

### Development Preview
`WATHIQ_AUTH_BYPASS` is development-only and is additionally gated by `NODE_ENV === 'development'`. It must never be enabled in production.

### Verification Center
The Verification Center feature is isolated under `features/verification` and composed of thin route files under `app/(dashboard)/dashboard/verification`.

The feature uses reusable components for verification lists, details, tabs, breadcrumbs, and navigation.

Verification types, labels, counts, routes, detail titles, and reference-field mappings are centralized in `features/verification/config/verification.config.js`, allowing future verification types to be added without duplicating page UI or business structure.