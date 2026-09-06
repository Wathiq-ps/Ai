# WATHIQ — Admin Dashboard Frontend (Phase 1)

Next.js 16 + React 19 frontend for the WATHIQ admin dashboard. Phase 1 focuses on the approved visual identity, responsive RTL/LTR UI, reusable components, and an API-ready authentication boundary.

## Stack

- Next.js 16 App Router
- React 19
- Tailwind CSS v4
- Recharts
- React Hook Form
- Lucide React
- Alexandria font

## Run locally

```bash
npm install
npm run dev
```

Then open `http://localhost:3000`.

## Environment

Copy `.env.example` to `.env.local` and set the Backend API base URL when the Laravel server is available. `.env.local` is ignored by Git and must not be committed.

The current auth endpoints are configurable through:

- `WATHIQ_OTP_REQUEST_PATH`
- `WATHIQ_OTP_VERIFY_PATH`
- `WATHIQ_AUTH_REFRESH_PATH`
- `WATHIQ_AUTH_LOGOUT_PATH`
- `WATHIQ_AUTH_ME_PATH`

`WATHIQ_AUTH_BYPASS` is for local development preview only and is additionally restricted in code to development mode.

## Phase 1 data

Dashboard content currently comes from `features/dashboard/data/dashboardMock.js`. This is intentional until the Backend team provides the dashboard API contract. API integration should happen in a service/hook layer and should not require rewriting the presentational dashboard sections.

## Design system

The canonical design tokens are defined in `app/globals.css` under Tailwind v4 `@theme`. Brand colors: `#002366`, `#B5C4FF`, `#FABD00`, and `#FFFFFF`. The project uses Alexandria and supports Arabic RTL / English LTR.

See `PROJECT_STRUCTURE.md` for architecture and handoff rules.

## Architecture

The frontend follows a feature-oriented and reusable architecture.

- `app/` — Next.js routes and layouts
- `components/` — shared UI and layout components
- `features/` — feature-specific modules
- `context/` — application-level state and providers
- `lib/` — API, authentication, and shared utilities
- `public/` — static assets

## Deployment

Live Preview: [Open WATHIQ Admin Dashboard](https://wathiq-frontend-44bfvkcuw-wathiq4.vercel.app?_vercel_share=dv2kbhANOh2x76wUjFzq8gkGAgJ2HHkm)
